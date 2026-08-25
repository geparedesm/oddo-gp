import base64
import binascii
import io
import logging

from PIL import Image as PILImage

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools import image_process

_logger = logging.getLogger(__name__)


class CommercialPropertyUnitImage(models.Model):
    _name = "commercial.property.unit.image"
    _description = "Commercial Property Unit Image"
    _order = "sequence, id"

    # Images whose decoded size is at or below this threshold are left
    # untouched (already small, e.g. optimized photos or test fixtures).
    _COMPRESSION_SIZE_THRESHOLD = 350 * 1024  # 350 KB
    _COMPRESSION_QUALITY = 85
    # A PNG -> JPEG conversion is only applied when the JPEG result is at
    # least 20% smaller than the same-format compressed result, so we never
    # swap formats for a marginal gain.
    _FORMAT_CONVERSION_GAIN_RATIO = 0.8

    unit_id = fields.Many2one(
        "commercial.property.unit",
        string="Unit",
        required=True,
        ondelete="cascade",
        index=True,
    )
    image_1920 = fields.Image(string="Photo", max_width=1920, max_height=1920)
    sequence = fields.Integer(default=10)
    name = fields.Char(string="Description")
    create_date = fields.Datetime(readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("image_1920"):
                vals["image_1920"] = self._compress_image_value(vals["image_1920"])
        return super().create(vals_list)

    def write(self, vals):
        if vals.get("image_1920"):
            vals = dict(vals, image_1920=self._compress_image_value(vals["image_1920"]))
        return super().write(vals)

    @api.model
    def _compress_image_value(self, image_value):
        """Recompress a base64-encoded image to reduce its byte size while
        keeping it visually equivalent. Returns the original value
        unchanged whenever compression cannot be safely applied or does
        not actually reduce the size (small/GIF fixtures, already
        optimized images, unreadable payloads, etc.).
        """
        if not image_value:
            return image_value

        try:
            decoded = base64.b64decode(image_value)
        except (TypeError, ValueError, binascii.Error):
            return image_value

        if not decoded or len(decoded) <= self._COMPRESSION_SIZE_THRESHOLD:
            return image_value

        try:
            original_format = (PILImage.open(io.BytesIO(decoded)).format or "").upper()
        except Exception:
            # Not a decodable image (corrupt payload); leave untouched and
            # let the standard field validation reject it if needed.
            return image_value

        try:
            best = image_process(
                decoded,
                size=(1920, 1920),
                quality=self._COMPRESSION_QUALITY,
                verify_resolution=True,
            )
        except (UserError, ValueError, OSError) as exc:
            _logger.warning("Skipping gallery image compression: %s", exc)
            return image_value

        if not best:
            return image_value

        if original_format == "PNG":
            try:
                as_jpeg = image_process(
                    decoded,
                    size=(1920, 1920),
                    quality=self._COMPRESSION_QUALITY,
                    verify_resolution=True,
                    output_format="JPEG",
                )
            except (UserError, ValueError, OSError) as exc:
                _logger.warning("Skipping PNG->JPEG gallery image conversion: %s", exc)
                as_jpeg = None
            if as_jpeg and len(as_jpeg) < len(best) * self._FORMAT_CONVERSION_GAIN_RATIO:
                best = as_jpeg

        if len(best) >= len(decoded):
            return image_value

        return base64.b64encode(best)

    @api.model
    def _compress_existing_gallery_images(self):
        """Recompress every existing gallery image. Safe to run multiple
        times: images that are already small enough or already optimized
        are skipped (write() only replaces the value when compression
        yields an actual byte-size reduction).
        """
        compressed_count = 0
        images = self.search([("image_1920", "!=", False)])
        for image in images:
            original = image.image_1920
            image.write({"image_1920": original})
            if image.image_1920 != original:
                compressed_count += 1
        return compressed_count
