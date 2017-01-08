import os
import hashlib
import logging

from PIL import Image as ImageFile, ImageFont, ImageDraw


log = logging.getLogger(__name__)


class Image(object):
    """JPEG generated by applying text to a template."""

    def __init__(self, template, text, root=None,
                 style=None, font=None, size=None):
        self.root = root
        self.template = template
        self.style = style
        self.text = text
        self.font = font
        self.width = size.get('width') if size else None
        self.height = size.get('height') if size else None

    @property
    def path(self):
        if not self.root:
            return None

        base = os.path.join(self.root, self.template.key, self.text.path)

        if self.style or self.font or self.width or self.height:
            slug = self.hash(self.style, self.font, self.width, self.height)
            return "{}#{}.img".format(base, slug)
        else:
            return base + ".img"

    @staticmethod
    def hash(*values):
        sha = hashlib.md5()
        for value in values:
            sha.update(str(value or "").encode('utf-8'))
        return sha.hexdigest()

    def save(self):
        data = _generate(
            top=self.text.top, bottom=self.text.bottom,
            font=self.font.path,
            background=self.template.get_path(self.style),
            width=self.width, height=self.height,
        )

        directory = os.path.dirname(self.path)
        if not os.path.isdir(directory):
            os.makedirs(directory)

        log.info("Saving image: %s", self.path)
        path = data.save(self.path, format=data.format)

        return path


# The following Pillow image functions are based on:
# https://github.com/danieldiekmeier/memegenerator


def _generate(top, bottom, font, background, width, height):
    """Add text to an image and save it."""
    log.info("Loading background: %s", background)
    image = ImageFile.open(background)
    if image.mode not in ('RGB', 'RGBA'):
        if image.format == 'JPEG':
            image = image.convert('RGB')
            image.format = 'JPEG'
        else:
            image = image.convert('RGBA')
            image.format = 'PNG'

    # Resize to a maximum height and width
    if width or height:
        max_dimensions = width or 2000, height or 2000
    else:
        max_dimensions = 400, 400
    image.thumbnail(max_dimensions)
    image_size = image.size

    # Draw image
    draw = ImageDraw.Draw(image)

    max_font_size = int(image_size[1] / 5)
    min_font_size_single_line = int(image_size[1] / 12)
    max_text_len = image_size[0] - 20
    top_font_size, top = _optimize_font_size(font, top, max_font_size,
                                             min_font_size_single_line,
                                             max_text_len)
    bottom_font_size, bottom = _optimize_font_size(font, bottom, max_font_size,
                                                   min_font_size_single_line,
                                                   max_text_len)

    top_font = ImageFont.truetype(font, top_font_size)
    bottom_font = ImageFont.truetype(font, bottom_font_size)

    top_text_size = draw.multiline_textsize(top, top_font)
    bottom_text_size = draw.multiline_textsize(bottom, bottom_font)

    # Find top centered position for top text
    top_text_position_x = (image_size[0] / 2) - (top_text_size[0] / 2)
    top_text_position_y = 0
    top_text_position = (top_text_position_x, top_text_position_y)

    # Find bottom centered position for bottom text
    bottom_text_size_x = (image_size[0] / 2) - (bottom_text_size[0] / 2)
    bottom_text_size_y = image_size[1] - bottom_text_size[1] * (7 / 6)
    bottom_text_position = (bottom_text_size_x, bottom_text_size_y)

    _draw_outlined_text(draw, top_text_position,
                        top, top_font, top_font_size)
    _draw_outlined_text(draw, bottom_text_position,
                        bottom, bottom_font, bottom_font_size)

    return image


def _draw_outlined_text(draw_image, text_position, text, font, font_size):
    """Draw white text with black outline on an image."""

    # Draw black text outlines
    outline_range = max(1, font_size // 25)
    for x in range(-outline_range, outline_range + 1):
        for y in range(-outline_range, outline_range + 1):
            pos = (text_position[0] + x, text_position[1] + y)
            draw_image.multiline_text(pos, text, (0, 0, 0),
                                      font=font, align='center')

    # Draw inner white text
    draw_image.multiline_text(text_position, text, (255, 255, 255),
                              font=font, align='center')


def _optimize_font_size(font, text, max_font_size, min_font_size,
                        max_text_len):
    """Calculate the optimal font size to fit text in a given size."""

    # Check size when using smallest single line font size
    fontobj = ImageFont.truetype(font, min_font_size)
    text_size = fontobj.getsize(text)

    # Calculate font size for text, split if necessary
    if text_size[0] > max_text_len:
        phrases = _split(text)
    else:
        phrases = (text,)
    font_size = max_font_size // len(phrases)
    for phrase in phrases:
        font_size = min(_maximize_font_size(font, phrase, max_text_len),
                        font_size)

    # Rebuild text with new lines
    text = '\n'.join(phrases)

    return font_size, text


def _maximize_font_size(font, text, max_size):
    """Find the biggest font size that will fit."""
    font_size = max_size

    fontobj = ImageFont.truetype(font, font_size)
    text_size = fontobj.getsize(text)
    while text_size[0] > max_size and font_size > 1:
        font_size = font_size - 1
        fontobj = ImageFont.truetype(font, font_size)
        text_size = fontobj.getsize(text)

    return font_size


def _split(text):
    """Split a line of text into two similarly sized pieces.

    >>> _split("Hello, world!")
    ('Hello,', 'world!')

    >>> _split("This is a phrase that can be split.")
    ('This is a phrase', 'that can be split.')

    >>> _split("This_is_a_phrase_that_can_not_be_split.")
    ('This_is_a_phrase_that_can_not_be_split.',)

    """
    result = (text,)

    if len(text) >= 3 and ' ' in text[1:-1]:  # can split this string
        space_indices = [i for i in range(len(text)) if text[i] == ' ']
        space_proximities = [abs(i - len(text) // 2) for i in space_indices]
        for i, j in zip(space_proximities, space_indices):
            if i == min(space_proximities):
                result = (text[:j], text[j + 1:])
                break

    return result
