/** Square avatar cropping helpers shared by every upload entry point. */

export const AVATAR_VIEWPORT = 280
export const AVATAR_OUTPUT_SIZE = 512

export type CropTransform = {
  zoom?: number
  offsetX?: number
  offsetY?: number
}

export const readImageFile = (file: File): Promise<string> =>
  new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result || ''))
    reader.onerror = () => reject(new Error('无法读取图片'))
    reader.readAsDataURL(file)
  })

const loadImage = (source: string): Promise<HTMLImageElement> =>
  new Promise((resolve, reject) => {
    const image = new Image()
    image.onload = () => resolve(image)
    image.onerror = () => reject(new Error('无法解析图片'))
    image.src = source
  })

/**
 * Crop the visible square area of the preview at `zoom`/`offset`, then encode it.
 * Offsets are expressed in preview pixels (the user's drag distance).
 */
export const cropAvatarFile = async (
  file: File,
  transform: CropTransform = {},
  viewport = AVATAR_VIEWPORT,
  outputSize = AVATAR_OUTPUT_SIZE,
): Promise<File> => {
  const dataUrl = await readImageFile(file)
  const image = await loadImage(dataUrl)

  const zoom = Math.min(3, Math.max(1, transform.zoom ?? 1))
  const offsetX = transform.offsetX ?? 0
  const offsetY = transform.offsetY ?? 0

  const coverScale = Math.max(viewport / image.naturalWidth, viewport / image.naturalHeight)
  const totalScale = coverScale * zoom
  const sourceSide = viewport / totalScale
  const centerX = image.naturalWidth / 2 - offsetX / totalScale
  const centerY = image.naturalHeight / 2 - offsetY / totalScale

  let sx = centerX - sourceSide / 2
  let sy = centerY - sourceSide / 2
  sx = Math.min(Math.max(sx, 0), Math.max(0, image.naturalWidth - sourceSide))
  sy = Math.min(Math.max(sy, 0), Math.max(0, image.naturalHeight - sourceSide))

  const canvas = document.createElement('canvas')
  canvas.width = outputSize
  canvas.height = outputSize
  const context = canvas.getContext('2d')
  if (!context) throw new Error('当前浏览器不支持头像裁剪')

  context.imageSmoothingQuality = 'high'
  context.drawImage(image, sx, sy, sourceSide, sourceSide, 0, 0, outputSize, outputSize)

  const blob = await new Promise<Blob | null>((resolve) => {
    canvas.toBlob(resolve, 'image/webp', 0.9)
  })
  if (!blob) throw new Error('头像编码失败')

  const baseName = file.name.replace(/\.[^.]+$/, '') || 'avatar'
  return new File([blob], `${baseName}-avatar.webp`, { type: 'image/webp' })
}
