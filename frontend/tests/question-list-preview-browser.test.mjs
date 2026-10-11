import assert from 'node:assert/strict'
import { spawn, spawnSync } from 'node:child_process'
import { existsSync, mkdirSync } from 'node:fs'
import { mkdtemp, readFile, rm, writeFile, unlink } from 'node:fs/promises'
import net from 'node:net'
import os from 'node:os'
import path from 'node:path'

const wait = (milliseconds) => new Promise((resolve) => setTimeout(resolve, milliseconds))

const getFreePort = () =>
  new Promise((resolve, reject) => {
    const server = net.createServer()
    server.once('error', reject)
    server.listen(0, '127.0.0.1', () => {
      const { port } = server.address()
      server.close(() => resolve(port))
    })
  })

const findChrome = () => {
  const candidates = [
    process.env.CHROME_PATH,
    'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
    'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe',
    '/usr/bin/google-chrome',
    '/usr/bin/google-chrome-stable',
    '/usr/bin/chromium',
    '/usr/bin/chromium-browser'
  ].filter(Boolean)
  return candidates.find((candidate) => existsSync(candidate))
}

const waitForHttp = async (url, label, timeoutMilliseconds = 15_000) => {
  const deadline = Date.now() + timeoutMilliseconds
  while (Date.now() < deadline) {
    try {
      const response = await fetch(url)
      if (response.ok) {
        return response
      }
    } catch {}
    await wait(100)
  }
  throw new Error(`${label} did not become ready: ${url}`)
}

const waitForFile = async (filePath, timeoutMilliseconds = 15_000) => {
  const deadline = Date.now() + timeoutMilliseconds
  while (Date.now() < deadline) {
    try {
      return await readFile(filePath, 'utf8')
    } catch {}
    await wait(100)
  }
  throw new Error(`Timed out waiting for ${filePath}`)
}

const connectCdp = async (url) => {
  const socket = new WebSocket(url)
  await new Promise((resolve, reject) => {
    socket.addEventListener('open', resolve, { once: true })
    socket.addEventListener('error', reject, { once: true })
  })
  let nextId = 1
  const pending = new Map()
  const exceptions = []
  socket.addEventListener('message', ({ data }) => {
    const message = JSON.parse(data)
    if (message.id && pending.has(message.id)) {
      const { resolve, reject } = pending.get(message.id)
      pending.delete(message.id)
      if (message.error) {
        reject(new Error(message.error.message))
      } else {
        resolve(message.result)
      }
    } else if (message.method === 'Runtime.exceptionThrown') {
      exceptions.push(JSON.stringify(message.params.exceptionDetails))
    }
  })
  const send = (method, params = {}) =>
    new Promise((resolve, reject) => {
      const id = nextId++
      pending.set(id, { resolve, reject })
      socket.send(JSON.stringify({ id, method, params }))
    })
  return { socket, send, exceptions }
}

const frontendRoot = path.resolve(import.meta.dirname, '..')
const repoRoot = path.resolve(frontendRoot, '..')
const base = 'a088acd192f4413c6914b01e368d608a5abd3fe7'
const chromePath = findChrome()
assert.ok(chromePath, 'Chrome/Chromium required')
const evidenceRoot = process.env.LIST_PREVIEW_EVIDENCE_DIR || path.join(os.tmpdir(), 'mks-issue152-evidence')
mkdirSync(evidenceRoot, { recursive: true })
const baselineFiles = []
const summaries = []
const vitePort = await getFreePort()
const profileDirectory = await mkdtemp(path.join(os.tmpdir(), 'mks-list-preview-'))
let viteProcess, chromeProcess, cdp
let viteLog = ''
try {
  for (const panel of ['Bank', 'History']) {
    const filename = path.join(frontendRoot, 'src/components', `__issue152Baseline${panel}.vue`)
    assert.equal(existsSync(filename), false, 'do not overwrite unknown fixture file')
    const source = spawnSync('git', ['-C', repoRoot, 'show', `${base}:frontend/src/components/${panel}Panel.vue`], {encoding:'utf8'})
    assert.equal(source.status, 0, source.stderr)
    await writeFile(filename, source.stdout)
    baselineFiles.push(filename)
  }
  viteProcess = spawn(process.execPath, [path.join(frontendRoot, 'node_modules/vite/bin/vite.js'), '--host', '127.0.0.1', '--port', String(vitePort), '--strictPort'], {cwd:frontendRoot,stdio:['ignore','pipe','pipe']})
  for (const stream of [viteProcess.stdout, viteProcess.stderr]) stream.on('data', chunk => { viteLog = (viteLog + chunk).slice(-12000) })
  await waitForHttp(`http://127.0.0.1:${vitePort}/tests/fixtures/question-list-preview.html`, 'Vite')
  chromeProcess = spawn(chromePath, ['--headless=new','--disable-gpu','--no-first-run','--no-default-browser-check','--remote-debugging-port=0',`--user-data-dir=${profileDirectory}`,'about:blank'], {stdio:['ignore','ignore','pipe']})
  const [debugPort] = (await waitForFile(path.join(profileDirectory, 'DevToolsActivePort'))).trim().split(/\r?\n/)
  const targets = await (await waitForHttp(`http://127.0.0.1:${debugPort}/json/list`, 'DevTools')).json()
  cdp = await connectCdp(targets.find(target => target.type === 'page').webSocketDebuggerUrl)
  await cdp.send('Runtime.enable')
  await cdp.send('Page.enable')
  await cdp.send('Network.enable')
  await cdp.send('Emulation.setDeviceMetricsOverride', {width:1280,height:960,deviceScaleFactor:1,mobile:false})
  const requestedImages = []
  cdp.socket.addEventListener('message', ({data}) => {
    const message = JSON.parse(data)
    if (message.method === 'Network.requestWillBeSent' && (message.params.type === 'Image' || message.params.request.url.includes('example.invalid'))) requestedImages.push(message.params.request.url)
  })
  for (const version of ['baseline', 'current']) {
    for (const panel of ['bank', 'trash', 'history']) {
      const imageStart = requestedImages.length
      await cdp.send('Page.navigate', {url:`http://127.0.0.1:${vitePort}/tests/fixtures/question-list-preview.html?version=${version}&panel=${panel}`})
      let result
      const deadline = Date.now() + 60_000
      while (Date.now() < deadline) {
        const evaluation = await cdp.send('Runtime.evaluate', {expression:'({ result: window.__listPreviewResult, error: window.__listPreviewError })',returnByValue:true})
        const state = evaluation.result.value
        if (state?.error) throw new Error(state.error)
        if (cdp.exceptions.length) throw new Error(cdp.exceptions.join('\n'))
        if (state?.result) { result = state.result; break }
        await wait(100)
      }
      if (!result) {
        const page = await cdp.send('Runtime.evaluate', {expression:'document.body.innerText', returnByValue:true})
        throw new Error(`${version}/${panel} fixture timed out\n${cdp.exceptions.join('\n')}\n${page.result.value}\n${viteLog}`)
      }
      const remoteImages = requestedImages.slice(imageStart).filter(url => !url.startsWith('data:') && !url.startsWith('blob:'))
      assert.deepEqual(remoteImages, [], 'remote list image requests must be zero')
      result.remoteImageRequests = remoteImages.length
      const median = key => {
        const values = result.results.map(row => row[key]).filter(value => value !== null).sort((a,b) => a-b)
        return values.length ? Number(values[Math.floor(values.length/2)].toFixed(2)) : null
      }
      result.medians = {mountMs:median('mountMs'),searchMs:median('searchMs'),selectionMs:median('selectionMs')}
      summaries.push(result)
      const screenshot = await cdp.send('Page.captureScreenshot', {format:'png',captureBeyondViewport:false})
      await writeFile(path.join(evidenceRoot, `${version}-${panel}.png`), Buffer.from(screenshot.data,'base64'))
      console.log(JSON.stringify({version,panel,rows:result.rows,medians:result.medians,remoteImageRequests:result.remoteImageRequests}))
    }
  }
  assert.deepEqual(cdp.exceptions, [])
  await writeFile(path.join(evidenceRoot, 'metrics.json'), JSON.stringify({base,fixture:'fixed synthetic data; mocked axios; five warm-module runs per panel/version; no real account/database/service',summaries},null,2))
  console.log(`List preview browser behavior/performance checks passed. Evidence: ${evidenceRoot}`)
} finally {
  cdp?.socket.close()
  chromeProcess?.kill()
  viteProcess?.kill()
  for (const filename of baselineFiles) await unlink(filename)
  await wait(200)
  await rm(profileDirectory, {recursive:true,force:true}).catch(() => {})
}
