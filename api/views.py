import io
import os
import json
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from PIL import Image


@csrf_exempt
def process_image(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST method required'}, status=405)
    
    try:
        width = int(request.POST.get('width', 132))
        height = int(request.POST.get('height', 170))
        min_size_kb = int(request.POST.get('minSize', 5))
        max_size_kb = int(request.POST.get('maxSize', 20))
        dpi = int(request.POST.get('dpi', 270))
        resize_algo = request.POST.get('resizeAlgorithm', 'Lanczos3')
        
        image_file = request.FILES.get('image')
        if not image_file:
            return JsonResponse({'error': 'No image provided'}, status=400)
            
        img = Image.open(image_file)
        
        # Convert to RGB, handling transparency
        if img.mode in ('RGBA', 'P', 'LA'):
            background = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'RGBA' or img.mode == 'LA':
                background.paste(img, mask=img.split()[-1])
            else:
                background.paste(img)
            img = background
        elif img.mode != 'RGB':
            img = img.convert('RGB')
            
        # Resizing
        if resize_algo == 'INTER_AREA':
            import cv2
            import numpy as np
            open_cv_image = np.array(img)
            open_cv_image = open_cv_image[:, :, ::-1].copy() # RGB to BGR
            resized = cv2.resize(open_cv_image, (width, height), interpolation=cv2.INTER_AREA)
            resized = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(resized)
        elif resize_algo == 'Bicubic Sharper':
            img = img.resize((width, height), resample=Image.Resampling.BICUBIC)
        else: # Default Lanczos3
            img = img.resize((width, height), resample=Image.Resampling.LANCZOS)
            
        # Smart Compression Logic
        min_bytes = min_size_kb * 1024
        max_bytes = max_size_kb * 1024
        
        quality = 100
        output_io = io.BytesIO()
        
        # Try maximum possible quality with no subsampling to get highest possible file size
        img.save(output_io, format='JPEG', quality=quality, dpi=(dpi, dpi), subsampling=0, optimize=False)
        size = output_io.tell()
        
        status = "unknown"
        
        if size > max_bytes:
            # Need to compress to get below max_bytes
            while quality >= 10:
                temp_io = io.BytesIO()
                img.save(temp_io, format='JPEG', quality=quality, dpi=(dpi, dpi), optimize=True)
                temp_size = temp_io.tell()
                
                if temp_size <= max_bytes:
                    output_io = temp_io
                    size = temp_size
                    if temp_size >= min_bytes:
                        status = "optimized"
                    else:
                        status = "below_minimum"
                    break
                        
                quality -= 5
                
            if status == "unknown":
                status = "exceeds_maximum"
                
        elif size < min_bytes:
            # Even at Q=100, 4:4:4, unoptimized, the file is smaller than min_bytes.
            status = "below_minimum"
            
        else:
            # Size naturally falls in [min_bytes, max_bytes] at max quality.
            status = "optimized"
            
        output_io.seek(0)
        
        response = HttpResponse(output_io.read(), content_type='image/jpeg')
        response['Content-Disposition'] = 'attachment; filename="processed_image.jpg"'
        # Attach processed stats in headers so frontend can display them
        response['X-Processed-Width'] = str(width)
        response['X-Processed-Height'] = str(height)
        response['X-Processed-DPI'] = str(dpi)
        response['X-Processed-Size'] = str(size)
        response['X-Processed-Quality'] = str(quality)
        response['X-Compression-Status'] = status
        response['Access-Control-Expose-Headers'] = 'X-Processed-Width, X-Processed-Height, X-Processed-DPI, X-Processed-Size, X-Processed-Quality, X-Compression-Status, Content-Disposition'
        
        return response
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
