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
        target_size_kb = int(request.POST.get('targetSize', 45))
        threshold_kb = int(request.POST.get('threshold', target_size_kb + 5))
        ideal_kb = int(request.POST.get('ideal', target_size_kb - 1))
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
        threshold_bytes = threshold_kb * 1024
        original_size_bytes = image_file.size
        
        quality = 100
        output_io = io.BytesIO()
        img.save(output_io, format='JPEG', quality=quality, dpi=(dpi, dpi))
        size = output_io.tell()
        
        status = "unknown"
        
        if original_size_bytes <= threshold_bytes:
            # Case 1: Original upload is small
            status = "original_small"
        else:
            # Case 2: Original is large
            if size <= (ideal_kb + 1) * 1024:
                # Naturally small at Q=100
                status = "naturally_small"
            else:
                # Needs compression
                while quality >= 10:
                    output_io.seek(0)
                    output_io.truncate()
                    img.save(output_io, format='JPEG', quality=quality, dpi=(dpi, dpi))
                    size = output_io.tell()
                    
                    if size <= (ideal_kb + 1) * 1024:
                        break
                        
                    quality -= 2
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
