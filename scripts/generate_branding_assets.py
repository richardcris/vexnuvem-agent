from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QImageReader, QLinearGradient, QPainter, QPainterPath, QPen


ROOT = Path(__file__).resolve().parents[1]
LOGO_PATH = ROOT / "logo.png"
OUTPUT_DIR = ROOT / "build_assets"
ICON_PATH = OUTPUT_DIR / "vexnuvem.ico"
WIZARD_IMAGE_PATH = OUTPUT_DIR / "installer_wizard.png"
SMALL_IMAGE_PATH = OUTPUT_DIR / "installer_small.png"


def load_logo() -> QImage:
    reader = QImageReader(str(LOGO_PATH))
    image = reader.read()
    if image.isNull():
        raise RuntimeError(f"Nao foi possivel carregar a logo em {LOGO_PATH}.")
    return image.convertToFormat(QImage.Format.Format_ARGB32)


def extract_center_square(image: QImage) -> QImage:
    side = min(image.width(), image.height())
    offset_x = max(0, (image.width() - side) // 2)
    offset_y = max(0, (image.height() - side) // 2)
    return image.copy(offset_x, offset_y, side, side)


def draw_contained(painter: QPainter, image: QImage, target: QRectF) -> None:
    source = QRectF(0, 0, image.width(), image.height())
    scaled = source.size()
    scaled.scale(target.size(), Qt.AspectRatioMode.KeepAspectRatio)
    x = target.x() + (target.width() - scaled.width()) / 2
    y = target.y() + (target.height() - scaled.height()) / 2
    painter.drawImage(QRectF(x, y, scaled.width(), scaled.height()), image, source)


def create_background(width: int, height: int) -> QImage:
    image = QImage(width, height, QImage.Format.Format_ARGB32)
    image.fill(QColor("#06111d"))
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

    gradient = QLinearGradient(QPointF(0, 0), QPointF(width, height))
    gradient.setColorAt(0.0, QColor("#07111f"))
    gradient.setColorAt(0.55, QColor("#0b1f33"))
    gradient.setColorAt(1.0, QColor("#05080d"))
    painter.fillRect(0, 0, width, height, gradient)

    glow = QPainterPath()
    glow.addRoundedRect(QRectF(width * 0.08, height * 0.06, width * 0.84, height * 0.88), 26, 26)
    painter.fillPath(glow, QColor(17, 119, 219, 28))

    pen = QPen(QColor(135, 205, 255, 62))
    pen.setWidth(2)
    painter.setPen(pen)
    painter.drawRoundedRect(QRectF(width * 0.08, height * 0.06, width * 0.84, height * 0.88), 26, 26)

    painter.end()
    return image


def create_icon(image: QImage) -> None:
    icon_image = QImage(256, 256, QImage.Format.Format_ARGB32)
    icon_image.fill(Qt.GlobalColor.transparent)

    painter = QPainter(icon_image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    draw_contained(painter, image, QRectF(10, 10, 236, 236))
    painter.end()

    if not icon_image.save(str(ICON_PATH)):
        raise RuntimeError(f"Nao foi possivel salvar o icone em {ICON_PATH}.")


def create_wizard_image(full_logo: QImage) -> None:
    canvas = create_background(240, 459)
    painter = QPainter(canvas)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    draw_contained(painter, full_logo, QRectF(12, 46, 216, 182))
    painter.end()

    if not canvas.save(str(WIZARD_IMAGE_PATH)):
        raise RuntimeError(f"Nao foi possivel salvar a imagem do instalador em {WIZARD_IMAGE_PATH}.")


def create_small_image(square_logo: QImage) -> None:
    canvas = create_background(147, 147)
    painter = QPainter(canvas)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    draw_contained(painter, square_logo, QRectF(10, 10, 127, 127))
    painter.end()

    if not canvas.save(str(SMALL_IMAGE_PATH)):
        raise RuntimeError(f"Nao foi possivel salvar a imagem pequena do instalador em {SMALL_IMAGE_PATH}.")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    full_logo = load_logo()
    square_logo = extract_center_square(full_logo)
    create_icon(square_logo)
    create_wizard_image(full_logo)
    create_small_image(square_logo)
    print(
        {
            "icon": str(ICON_PATH),
            "wizard": str(WIZARD_IMAGE_PATH),
            "small": str(SMALL_IMAGE_PATH),
        }
    )


if __name__ == "__main__":
    main()