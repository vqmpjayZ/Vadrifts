from PIL import Image, ImageFilter
from io import BytesIO
import requests
import time
import logging
from flask import jsonify

logger = logging.getLogger(__name__)

def resize_with_crop(image, target_size=(32, 32)):
    ow, oh = image.size
    tw, th = target_size
    scale = max(tw / ow, th / oh)
    nw = int(ow * scale)
    nh = int(oh * scale)
    image = image.resize((nw, nh), Image.LANCZOS)
    left = (nw - tw) // 2
    top = (nh - th) // 2
    return image.crop((left, top, left + tw, top + th))

def convert_image_endpoint(request):
    start_time = time.time()

    image_url = request.args.get('url')
    crop_mode = request.args.get('crop', 'true').lower() == 'true'
    simple_mode = request.args.get('simple', 'false').lower() == 'true'

    if not image_url:
        return jsonify({'error': 'No URL provided in query parameters'}), 400

    try:
        response = requests.get(image_url, timeout=15)
        if response.status_code != 200:
            return jsonify({'error': f'Failed to fetch image: HTTP {response.status_code}'}), 500

        image = Image.open(BytesIO(response.content))
        if image.mode != 'RGB':
            image = image.convert('RGB')

        original_size = image.size

        if simple_mode:
            image = resize_with_crop(image, (64, 64))
            image = image.resize((32, 32), Image.NEAREST)
            resize_method = "simple"
        else:
            if crop_mode:
                image = resize_with_crop(image, (32, 32))
                resize_method = "crop"
            else:
                image = image.resize((32, 32), Image.LANCZOS)
                resize_method = "simple_resize"

        pixels = []
        for y in range(32):
            for x in range(32):
                r, g, b = image.getpixel((x, y))
                pixels.append({'R': r, 'G': g, 'B': b})

        return jsonify({
            'pixels': pixels,
            'processing_time': time.time() - start_time,
            'original_size': original_size,
            'final_size': [32, 32],
            'resize_method': resize_method,
            'crop_mode': crop_mode,
            'simple_mode': simple_mode
        })

    except requests.exceptions.Timeout:
        return jsonify({'error': 'Request timed out'}), 504
    except Exception as e:
        logger.error(f"Image conversion error: {e}")
        return jsonify({'error': str(e)}), 500
