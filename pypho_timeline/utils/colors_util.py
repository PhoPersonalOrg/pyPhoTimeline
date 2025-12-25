"""Color utility functions for generating unique colors."""

import hashlib


class ColorsUtil:
    """Utility class for color generation and manipulation."""
    
    @staticmethod
    def generate_unique_hex_color_from_hashable(hashable_key) -> str:
        """Generate a consistent unique hex color from a hashable key.
        
        Args:
            hashable_key: Any hashable object (e.g., string, tuple) to use as seed
            
        Returns:
            Hex color string in format '#RRGGBB'
        """
        # Create a hash from the key
        key_str = str(hashable_key).encode('utf-8')
        hash_obj = hashlib.md5(key_str)
        hash_int = int(hash_obj.hexdigest()[:6], 16)
        
        # Use the hash to generate RGB values
        # Ensure colors are not too dark or too light for visibility
        r = (hash_int & 0xFF0000) >> 16
        g = (hash_int & 0x00FF00) >> 8
        b = hash_int & 0x0000FF
        
        # Adjust to ensure reasonable brightness (avoid very dark colors)
        min_brightness = 80
        max_brightness = 220
        r = max(min_brightness, min(max_brightness, r))
        g = max(min_brightness, min(max_brightness, g))
        b = max(min_brightness, min(max_brightness, b))
        
        return f"#{r:02x}{g:02x}{b:02x}"

