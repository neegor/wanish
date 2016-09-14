import re
from urllib.parse import urlparse, urljoin
import requests
from requests.exceptions import Timeout
import struct
from io import BytesIO

MIN_IMAGE_WIDTH = 400  # px
MIN_IMAGE_HEIGHT = 225  # px

MAX_DIMENSION_RATIO = 3  # maximum ratio of dimensions, if higher - we consider it a banner

# TODO: fill it with more data, getting only good JPG/PNG images
IGNORE_PATH_REGULAR = re.compile(
    ".gif|.ico|twitter.jpg|share|social|logo|/ads.|/ads/|button"
)

# TODO: fill it with more data, getting only good JPG/PNG images
GOOD_PATH_REGULAR = re.compile(
    ".jpg|.jpeg|.png"
)

IMG_DOWNLOAD_TIMEOUT = 5  # sec


class Image(object):
    """
    represents an image in given article
    """
    url = None
    width = 0  # width of an image
    height = 0  # height of an image
    area = 0  # area of an image, width * height
    is_good = False  # if it is a good candidate to be an image

    def __init__(self, img_node=None, html_url=None, headers=None):
        """
        retrieving image's parameters
        :param img_node: node of the img tag
        :param html_url: url of the source page
        :param headers: extra headers to request for images' data
        """

        self.url = self.absolute_url(img_node.get('src'), html_url)

        if self.url is not None:

            path = urlparse(self.url).path
            if not IGNORE_PATH_REGULAR.search(path) and GOOD_PATH_REGULAR.search(path):

                try:
                    # getting its dimensions
                    self.width = int(img_node.get('width', 0))
                    self.height = int(img_node.get('height', 0))
                except ValueError:
                    self.width, self.height = 0, 0

                # TODO: need a way to do it also by css styles

                # if dimensions are not found, getting dimensions of the image itself
                if self.width == 0 or self.height == 0:
                    self.width, self.height = self.fetch_image_dimensions(self.url, headers=headers)

                self.area = self.width * self.height

                if self.width >= MIN_IMAGE_WIDTH and self.height >= MIN_IMAGE_HEIGHT:

                    # checking if it is banner-like
                    is_banner = self.possible_banner()
                    if not is_banner:
                        self.is_good = True

    def possible_banner(self):
        """
        checks if given image is looking like banner
        :return: True or False
        """
        if self.width == 0 or self.height == 0:
            return True
        else:
            dim_ratio = self.width / self.height if self.width > self.height else self.height / self.width
            return dim_ratio > MAX_DIMENSION_RATIO

    @staticmethod
    def absolute_url(image_url, source_url):
        """
        makes image path absolute if it is relative
        :param image_url: url of an image
        :param source_url: url of the source page
        :return: absolute url or None
        """
        if image_url is None:
            return None

        parsed_img = urlparse(image_url)

        if parsed_img.hostname is None:
            if source_url is None:
                return None
            else:
                return urljoin(source_url, image_url)
        else:
            return image_url

    # http://stackoverflow.com/questions/8032642/how-to-obtain-image-size-using-standard-python-class-without-using-external-lib
    @staticmethod
    def fetch_image_dimensions(img_url, headers=None):
        """
        detects format of the image and returns its width and height from meta
        :param img_url: url of the image
        :param headers: extra headers for url requests if needed
        :return: image's width and height
        """
        width = -1
        height = -1
        try:
            r = requests.get(url=img_url, timeout=IMG_DOWNLOAD_TIMEOUT, headers=headers)
            head = r.content[:32]
            if head.startswith(b'\211PNG\r\n\032\n'):
                check = struct.unpack('>i', head[4:8])[0]
                if check != 0x0d0a1a0a:
                    return width, height
                width, height = struct.unpack('>ii', head[16:24])
            elif head[:6] in (b'GIF87a', b'GIF89a'):
                width, height = struct.unpack('<HH', head[6:10])
            elif head[6:10] in (b'JFIF', b'Exif'):
                fhandle = r.content
                try:
                    fhandle = BytesIO(fhandle)
                    fhandle.seek(0)  # Read 0xff next
                    size = 2
                    ftype = 0
                    while not 0xc0 <= ftype <= 0xcf:
                        fhandle.seek(size, 1)
                        byte = fhandle.read(1)
                        while ord(byte) == 0xff:
                            byte = fhandle.read(1)
                        ftype = ord(byte)
                        size = struct.unpack('>H', fhandle.read(2))[0] - 2
                    # We are at a SOFn block
                    fhandle.seek(1, 1)  # Skip `precision' byte.
                    height, width = struct.unpack('>HH', fhandle.read(4))
                except Exception:  # IGNORE:W0703
                    return width, height
        except (Timeout, TypeError):
            pass
        return width, height

    def __str__(self):
        # TODO: for debug purposes,. remove it later
        return ("%s (%sx%s, area: %s) - %s" % (
            self.url,
            self.width,
            self.height,
            self.area,
            "GOOD" if self.is_good else "bad"
        ))


def get_image_url(html, source_url=None, headers=None):
    """
    gets article picture's url

    # Algorithm:
    # 1. Get a list of image urls in html
    # 2. Filter out unsuitable images (ads, gifs, icons, buttons)
    # 3. Receive images dimensions (height, width)
    # 4. Sort them by their square and order of appearance, removing banner-like images (too thin or too tall)
    # 5. Get the first as a result

    :param html: html page element
    :param source_url: url of the source html page, used for normalization of img links
    :param headers: headers to send when detecting dimensions of images
    :return: url of the image
    """

    # Get all img urls
    image_nodes = html.xpath("//img")

    candidates_list = list()

    # find good candidates
    for node in image_nodes:
        image = Image(img_node=node, html_url=source_url, headers=headers)
        if image.is_good is True:
            candidates_list.append(image)

    # sort the list by area of images
    candidates_list.sort(key=lambda x: x.area, reverse=True)

    # return top-most url
    return candidates_list[0].url if len(candidates_list) > 0 else None
