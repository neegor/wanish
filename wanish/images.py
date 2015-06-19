from urllib.parse import urlparse, urljoin
import requests
from requests.exceptions import Timeout
import struct
from io import BytesIO

MIN_IMG_WIDTH = 500  # px
MIN_IMG_HEIGHT = 225  # px

IMG_DOWNLOAD_TIMEOUT = 5  # sec

# markers for logo stubs that do not represent actual image of the article
LOGO_STUBS = ['logo', 'fb', 'og', 'default', 'share', 'facebook', 'social']


def get_image_url(html, source_url=None):
    """
    Getting image url from headline or page meta and validating it
    :param html: html page element
    :param source_url: url of the source html page, used for normalization of img links
    :return: url of the image
    """

    # gettng images' urls from micro formats
    images_data = html.xpath("//img[@itemprop='image']/@src")
    if len(images_data) == 0:
        images_data = html.xpath("//img[@itemprop='associatedMedia']/@src")
    if len(images_data) == 0:
        images_data = html.xpath("//meta[@*='og:image']/@content")

    try:
        image_url = images_data[0]
        parsed_url = urlparse(image_url)

        # making image url absolute if needed
        if len(parsed_url.netloc.strip()) == 0 and source_url is not None:
            parsed_src_url = urlparse(source_url)
            if len(parsed_src_url.netloc.strip()) > 0:
                image_url = urljoin('%s://%s' % (parsed_src_url.scheme, parsed_src_url.netloc), parsed_url.path)

        # check if it has adequate extension and not a popular logo stub
        if (parsed_url.path.split('.')[-1] in ['jpg', 'jpeg', 'gif', 'png']) \
                and not any(sub in parsed_url.path for sub in LOGO_STUBS):

            # getting it's width and height, checking for size - stubs are usually not so wide
            w, h = fetch_image_data(image_url)
            if w < MIN_IMG_WIDTH:
                return None
            return image_url
        else:
            return None
    except IndexError:
        pass
    return None


# http://stackoverflow.com/questions/8032642/how-to-obtain-image-size-using-standard-python-class-without-using-external-lib
def fetch_image_data(img_url):
    """
    detects format of the image and returns its width and height from meta
    :param img_url: url of the image
    :return: image's width and height
    """
    width = -1
    height = -1
    try:
        r = requests.get(url=img_url, timeout=IMG_DOWNLOAD_TIMEOUT)
        head = r.content[:32]
        if head.startswith(b'\211PNG\r\n\032\n'):
            check = struct.unpack('>i', head[4:8])[0]
            if check != 0x0d0a1a0a:
                return
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
                return
    except (Timeout, TypeError):
        pass
    return width, height
