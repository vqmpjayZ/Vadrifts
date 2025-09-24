from PIL import Image
from io import BytesIO
import requests
import time
import logging
from flask import jsonify

logger = logging.getLogger(__name__)

def resize_with_crop(image, target_size=(32, 32)):
    original_width, original_height = image.size
    target_width, target_height = target_size
    
    scale_w = target_width / original_width
    scale_h = target_height / original_height
    scale = max(scale_w, scale_h)
    
    new_width = int(original_width * scale)
    new_height = int(original_height * scale)
    
    resized_image = image.resize((new_width, new_height), Image.LANCZOS)

    left = (new_width - target_width) // 2
    top = (new_height - target_height) // 2
    right = left + target_width
    bottom = top + target_height

    cropped_image = resized_image.crop((left, top, right, bottom))
    
    return cropped_image

def convert_image_endpoint(request):
    start_time = time.time()
    
    image_url = request.args.get('url')
    crop_mode = request.args.get('crop', 'true').lower() == 'true'
    
    if not image_url:
        return jsonify({'error': 'No URL provided in query parameters'}), 400
    
    logger.info(f"Processing image from URL: {image_url}, crop_mode: {crop_mode}")
    
    try:
        response = requests.get(image_url, timeout=15)
        if response.status_code != 200:
            return jsonify({'error': f'Failed to fetch image: HTTP {response.status_code}'}), 500
        
        image = Image.open(BytesIO(response.content))
        
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        original_size = image.size
        
        if crop_mode:
            image = resize_with_crop(image, (32, 32))
            resize_method = "crop"
        else:
            image = image.resize((32, 32), Image.LANCZOS)
            resize_method = "simple_resize"
        
        pixels = []
        for y in range(image.height):
            for x in range(image.width):
                pixel = image.getpixel((x, y))
                if len(pixel) >= 3:
                    r, g, b = pixel[:3]
                else:
                    r = g = b = pixel if isinstance(pixel, int) else pixel[0]
                pixels.append({'R': r, 'G': g, 'B': b})
        
        processing_time = time.time() - start_time
        
        return jsonify({
            'pixels': pixels,
            'processing_time': processing_time,
            'original_size': original_size,
            'final_size': [32, 32],
            'resize_method': resize_method,
            'crop_mode': crop_mode
        })
        
    except requests.exceptions.Timeout:
        return jsonify({'error': 'Request timed out'}), 504
    except Exception as e:
        logger.error(f"Image conversion error: {e}")
        return jsonify({'error': str(e)}), 500
