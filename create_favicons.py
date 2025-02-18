from PIL import Image
import os

def create_favicons():
    # Source image path
    source_path = 'LOS_watermark_red.png'
    favicon_dir = 'app/static/img/favicon'
    
    # Create favicon directory if it doesn't exist
    os.makedirs(favicon_dir, exist_ok=True)
    
    # Open the source image
    with Image.open(source_path) as img:
        # Convert to RGBA if not already
        img = img.convert('RGBA')
        
        # Define the sizes needed
        sizes = {
            'android-chrome-512x512.png': (512, 512),
            'android-chrome-192x192.png': (192, 192),
            'apple-touch-icon.png': (120, 120),
            'favicon-32x32.png': (32, 32),
            'favicon-16x16.png': (16, 16)
        }
        
        # Create each size
        for filename, size in sizes.items():
            resized = img.resize(size, Image.Resampling.LANCZOS)
            output_path = os.path.join(favicon_dir, filename)
            # Save with transparency
            resized.save(output_path, 'PNG')
            print(f'Created {output_path}')
        
        # Create ICO file (Windows favicon)
        favicon_path = os.path.join(favicon_dir, 'favicon.ico')
        ico_sizes = [(16, 16), (32, 32)]
        ico_images = [img.resize(size, Image.Resampling.LANCZOS) for size in ico_sizes]
        ico_images[0].save(favicon_path, format='ICO', sizes=[(16, 16), (32, 32)])
        print(f'Created {favicon_path}')

if __name__ == '__main__':
    create_favicons()
