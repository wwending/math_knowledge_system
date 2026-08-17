import { createApp, h, nextTick, ref } from 'vue'
import { VueCropper } from 'vue-cropper'
import 'vue-cropper/dist/index.css'

const SOURCE_WIDTH = 4961
const SOURCE_HEIGHT = 7016
const VIEWPORT_WIDTH = 960
const VIEWPORT_HEIGHT = 480
const TARGET_CROP_WIDTH = 2400
const TARGET_CROP_HEIGHT = 600

const wait = (milliseconds) => new Promise((resolve) => setTimeout(resolve, milliseconds))

const makeSource = () => {
  const canvas = document.createElement('canvas')
  canvas.width = SOURCE_WIDTH
  canvas.height = SOURCE_HEIGHT
  const context = canvas.getContext('2d')
  context.fillStyle = '#fff'
  context.fillRect(0, 0, canvas.width, canvas.height)
  context.fillStyle = '#13252f'
  context.font = '64px sans-serif'
  for (let y = 160; y < SOURCE_HEIGHT; y += 180) {
    context.fillText(`数学题定位行 ${Math.round(y / 180)}：χ²  α  0.01  6.635`, 140, y)
  }
  context.strokeStyle = '#4d7285'
  context.lineWidth = 5
  context.strokeRect(120, 120, SOURCE_WIDTH - 240, SOURCE_HEIGHT - 240)
  return canvas.toDataURL('image/jpeg', 0.92)
}

const decodeBlob = async (blob) => {
  const url = URL.createObjectURL(blob)
  try {
    const image = new Image()
    image.src = url
    await image.decode()
    return { width: image.naturalWidth, height: image.naturalHeight }
  } finally {
    URL.revokeObjectURL(url)
  }
}

const cropBlob = (cropper) => new Promise((resolve) => cropper.getCropBlob(resolve))

const runMode = (mode, source) =>
  new Promise((resolve, reject) => {
    const fixture = document.querySelector('#fixture')
    fixture.replaceChildren()
    const cropperRef = ref(null)
    let completed = false

    const finish = async (status) => {
      if (status !== 'success' || completed) {
        if (status !== 'success') {
          reject(new Error(`vue-cropper failed to load fixture image: ${String(status)}`))
        }
        return
      }
      completed = true
      try {
        await nextTick()
        await wait(80)
        const cropper = cropperRef.value
        const initialScale = cropper.scale
        const initialAxis = cropper.getImgAxis()

        cropper.changeCrop(TARGET_CROP_WIDTH * initialScale, TARGET_CROP_HEIGHT * initialScale)
        await nextTick()
        await wait(40)

        const cropAxis = cropper.getCropAxis()
        const blob = await cropBlob(cropper)
        const decoded = await decodeBlob(blob)
        const infoText = fixture.querySelector('.crop-info')?.textContent?.trim() || ''

        const beforeCropMove = cropper.getCropAxis()
        cropper.cropMove({
          preventDefault() {},
          clientX: beforeCropMove.x1 + 10,
          clientY: beforeCropMove.y1 + 10
        })
        cropper.moveCrop({
          preventDefault() {},
          clientX: beforeCropMove.x1 + 60,
          clientY: beforeCropMove.y1 + 30
        })
        await nextTick()
        const afterCropMove = cropper.getCropAxis()
        cropper.leaveCrop()

        const beforePan = cropper.getImgAxis()
        cropper.startMove({ preventDefault() {}, clientX: 20, clientY: 20, offsetX: 20, offsetY: 20 })
        cropper.moveImg({ preventDefault() {}, clientX: 20, clientY: -80 })
        await nextTick()
        const afterPan = cropper.getImgAxis()
        cropper.leaveImg()

        const beforeZoomScale = cropper.scale
        cropper.changeScale(10)
        await nextTick()
        const afterZoomScale = cropper.scale

        resolve({
          mode,
          viewport: { width: cropper.w, height: cropper.h },
          source: { width: SOURCE_WIDTH, height: SOURCE_HEIGHT },
          internalBitmap: { width: cropper.trueWidth, height: cropper.trueHeight },
          displayedImage: {
            width: initialAxis.x2 - initialAxis.x1,
            height: initialAxis.y2 - initialAxis.y1
          },
          cropCss: {
            width: cropAxis.x2 - cropAxis.x1,
            height: cropAxis.y2 - cropAxis.y1
          },
          cropBlob: { ...decoded, mime: blob.type, bytes: blob.size },
          infoText,
          canMove: cropper.canMove,
          canMoveBox: cropper.canMoveBox,
          canScale: cropper.canScale,
          cropMoveDelta: {
            x: afterCropMove.x1 - beforeCropMove.x1,
            y: afterCropMove.y1 - beforeCropMove.y1
          },
          panDeltaY: afterPan.y1 - beforePan.y1,
          zoomScaleDelta: afterZoomScale - beforeZoomScale
        })
      } catch (error) {
        reject(error)
      }
    }

    createApp({
      setup() {
        return () =>
          h(VueCropper, {
            ref: cropperRef,
            img: source,
            outputSize: 1,
            outputType: 'png',
            maxImgSize: SOURCE_HEIGHT,
            autoCrop: true,
            centerBox: true,
            canMove: true,
            canMoveBox: true,
            canScale: true,
            fixedBox: false,
            full: true,
            high: true,
            infoTrue: true,
            mode,
            onImgLoad: finish
          })
      }
    }).mount(fixture)
  })

window.__cropperViewportResult = null
window.__cropperViewportError = null

try {
  const source = makeSource()
  const contain = await runMode('contain', source)
  const cover = await runMode('cover', source)
  window.__cropperViewportResult = { contain, cover }
} catch (error) {
  window.__cropperViewportError = error?.stack || String(error)
}
