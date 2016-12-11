import re
from urllib.parse import urlparse, urljoin
import requests
from requests.exceptions import Timeout
import struct
from io import BytesIO

MIN_IMAGE_WIDTH = 580  # px
MIN_IMAGE_HEIGHT = 250  # px

MAX_DIMENSION_RATIO = 3  # maximum ratio of dimensions, if higher - we consider it a banner

# TODO: fill it with more data, getting only good JPG/PNG images
IGNORE_PATH_REGULAR = re.compile(
    r".gif|.ico|twitter.jpg|share|social|logo|/ads.|/ads/|button|notification"
)

# TODO: fill it with more data, getting only good JPG/PNG images
GOOD_PATH_REGULAR = re.compile(
    r".jpg|.jpeg|.png"
)

IMAGE_URL_FROM_STRING_REGULAR = re.compile(
    r"(http|ftp|https)://([\w_-]+(?:(?:\.[\w_-]+)+))([\w.,@?^=%:/~+#-]*(.jpg|.jpeg|.png))?"
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

        # getting url of the given img node
        self.url = self.get_image_url_from_node(img_node, html_url)

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

    def deparameterize_url(self, image_url):
        """
        checks if real image url is a parameter given to some page
        :param image_url: initial url
        :return: resulting url
        """
        try:
            if self.validate_img_url(image_url) is True:
                return image_url

            match = IMAGE_URL_FROM_STRING_REGULAR.search(urlparse(image_url).query)
            if match is not None:
                return match.group()
        except TypeError:
            pass

        return image_url

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
        try:
            parsed_img = urlparse(image_url)

            if parsed_img.hostname is None:
                if source_url is None:
                    return None
                else:
                    return urljoin(source_url, image_url)
            else:
                return image_url
        except TypeError:
            return None

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
        except (Timeout, TypeError, ConnectionError):
            pass
        return width, height

    def get_image_url_from_node(self, img_node, source_url, min_srcset_res=600):

        # checking adaptive 'srcset' attribute
        srcset = img_node.get('srcset')
        if srcset is not None:
            first_good_url = None
            for entry in srcset.split(','):
                entry = entry.strip()
                try:
                    data = entry.split()
                    url = data[0]
                    res = int(re.sub("\D", "", data[1]))
                    url = self.absolute_url(url, source_url)
                    if self.validate_img_url(url) is True:
                        if res >= min_srcset_res:
                            return url
                        if first_good_url is None:
                            first_good_url = url
                except IndexError as e:
                    pass

            if first_good_url is not None:
                return first_good_url

        # checking src attribute
        img_url = img_node.get('src')
        if img_url is not None:
            img_url = self.absolute_url(img_url, source_url)
            if self.validate_img_url(img_url) is True:
                return img_url

        # checking all 'data*' attributes
        for key, value in img_node.attrib.items():
            if key.startswith('data'):
                img_url = self.absolute_url(value, source_url)
                if self.validate_img_url(img_url) is True:
                    return self.deparameterize_url(img_url)

        return None

    @staticmethod
    def validate_img_url(url):
        try:
            parsed = urlparse(url)
            return parsed.path.endswith(('.jpg', 'jpeg', 'png',))
        except TypeError:
            return False

    def __str__(self):
        # TODO: for debug purposes,. remove it later
        return ("%s (%sx%s, area: %s) - %s" % (
            self.url,
            self.width,
            self.height,
            self.area,
            "GOOD" if self.is_good else "bad"
        ))


def get_image_container_node(html=None, article=None, title=None):
    """
    Returns first enveloping parent node for given title node
    :param html: page element
    :param article: element containing article
    :param title: element containing title
    :return:
    """

    if article is not None and title is not None:
        article_parents = [ap for ap in article.iterancestors()]

        for tp in title.iterancestors():
            if tp in article_parents:
                return tp
    return html


def get_image_url(html, source_url=None, headers=None, article_element=None, title_element=None):
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
    :param article_element: detected article element to improve image detection
    :param title_element: detected title element to improve image detection
    :return: url of the image
    """

    # Get container element of a title: usually the article-related images are in the same block with title and article
    container_node = get_image_container_node(html, article_element, title_element)

    # Get all img urls
    image_nodes = container_node.xpath(".//img")

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
