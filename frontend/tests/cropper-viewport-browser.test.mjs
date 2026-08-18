import assert from 'node:assert/strict'
import { spawn } from 'node:child_process'
import { existsSync } from 'node:fs'
import { mkdtemp, readFile, rm, writeFile } from 'node:fs/promises'
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
      exceptions.push(message.params.exceptionDetails.text)
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
const chromePath = findChrome()
assert.ok(chromePath, 'Chrome/Chromium is required for the vue-cropper browser behavior test')

const vitePort = await getFreePort()
const profileDirectory = await mkdtemp(path.join(os.tmpdir(), 'mks-cropper-browser-'))
const viteProcess = spawn(
  process.execPath,
  [path.join(frontendRoot, 'node_modules/vite/bin/vite.js'), '--host', '127.0.0.1', '--port', String(vitePort), '--strictPort'],
  { cwd: frontendRoot, stdio: ['ignore', 'pipe', 'pipe'] }
)
let chromeProcess
let cdp

try {
  const fixtureUrl = `http://127.0.0.1:${vitePort}/tests/fixtures/cropper-viewport.html`
  await waitForHttp(fixtureUrl, 'Vite fixture server')

  chromeProcess = spawn(
    chromePath,
    [
      '--headless=new',
      '--no-sandbox',
      '--disable-gpu-sandbox',
      '--disable-dev-shm-usage',
      '--disable-gpu',
      '--no-first-run',
      '--no-default-browser-check',
      '--remote-debugging-port=0',
      `--user-data-dir=${profileDirectory}`,
      'about:blank'
    ],
    { stdio: ['ignore', 'ignore', 'pipe'] }
  )

  const activePort = await waitForFile(path.join(profileDirectory, 'DevToolsActivePort'))
  const [debugPort] = activePort.trim().split(/\r?\n/)
  const targetsResponse = await waitForHttp(`http://127.0.0.1:${debugPort}/json/list`, 'Chrome DevTools')
  const targets = await targetsResponse.json()
  const pageTarget = targets.find((target) => target.type === 'page')
  assert.ok(pageTarget?.webSocketDebuggerUrl, 'Chrome did not expose a debuggable page target')

  cdp = await connectCdp(pageTarget.webSocketDebuggerUrl)
  await cdp.send('Runtime.enable')
  await cdp.send('Page.enable')
  await cdp.send('Emulation.setDeviceMetricsOverride', {
    width: 1200,
    height: 900,
    deviceScaleFactor: 1,
    mobile: false
  })
  await cdp.send('Page.navigate', { url: fixtureUrl })

  let result
  const deadline = Date.now() + 45_000
  while (Date.now() < deadline) {
    const evaluation = await cdp.send('Runtime.evaluate', {
      expression: '({ result: window.__cropperViewportResult, error: window.__cropperViewportError })',
      returnByValue: true
    })
    const state = evaluation.result.value
    if (state?.error) {
      throw new Error(state.error)
    }
    if (state?.result) {
      result = state.result
      break
    }
    await wait(100)
  }
  assert.ok(result, 'vue-cropper fixture did not produce viewport metrics')
  assert.deepEqual(cdp.exceptions, [], `Browser runtime exceptions: ${cdp.exceptions.join('; ')}`)

  const { contain, cover } = result
  assert.deepEqual(contain.viewport, { width: 960, height: 480 })
  assert.deepEqual(cover.viewport, { width: 960, height: 480 })
  assert.deepEqual(contain.source, { width: 4961, height: 7016 })
  assert.deepEqual(cover.source, contain.source)
  assert.deepEqual(contain.internalBitmap, contain.source, 'contain must preserve the high-resolution bitmap')
  assert.deepEqual(cover.internalBitmap, cover.source, 'cover must preserve the high-resolution bitmap')
  assert.ok(contain.displayedImage.width < 350, `contain width was ${contain.displayedImage.width}`)
  assert.ok(cover.displayedImage.width >= 959, `cover width was ${cover.displayedImage.width}`)
  assert.ok(cover.displayedImage.width >= contain.displayedImage.width * 2.7)
  assert.ok(cover.displayedImage.height > cover.viewport.height, 'cover must leave vertical content available by panning')
  assert.equal(cover.canMove, true)
  assert.equal(cover.canMoveBox, true)
  assert.equal(cover.canScale, true)
  assert.ok(Math.abs(cover.cropMoveDelta.x) > 1, 'cover crop box did not move horizontally')
  assert.ok(Math.abs(cover.cropMoveDelta.y) > 1, 'cover crop box did not move vertically')
  assert.ok(Math.abs(cover.panDeltaY) > 1, 'cover image did not move vertically')
  assert.ok(cover.zoomScaleDelta > 0, 'changeScale() did not zoom the image')

  for (const metrics of [contain, cover]) {
    assert.equal(metrics.cropBlob.width, 2400)
    assert.equal(metrics.cropBlob.height, 600)
    assert.equal(metrics.cropBlob.mime, 'image/png')
    assert.equal(metrics.infoText, '2400 × 600')
    assert.ok(metrics.cropBlob.width > metrics.cropCss.width, `${metrics.mode} crop fell back to CSS width`)
  }

  if (process.env.CROPPER_SCREENSHOT_PATH) {
    const screenshot = await cdp.send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: true })
    await writeFile(process.env.CROPPER_SCREENSHOT_PATH, Buffer.from(screenshot.data, 'base64'))
  }

  console.log(JSON.stringify(result, null, 2))
  console.log('vue-cropper viewport browser behavior tests passed.')
} finally {
  cdp?.socket.close()
  chromeProcess?.kill()
  viteProcess.kill()
  await wait(200)
  await rm(profileDirectory, { recursive: true, force: true }).catch(() => {})
}
