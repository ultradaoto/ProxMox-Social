"""
Fast image comparison for validation.
Optimized for 100x100 pixel images.
"""
import io
import hashlib
from typing import Tuple
from PIL import Image
import numpy as np


class ImageComparator:
    """
    Compares images using multiple algorithms.
    Optimized for speed on small images.
    """
    
    def __init__(self, algorithm: str = 'structural_similarity'):
        """
        Initialize comparator.
        
        Args:
            algorithm: Comparison algorithm
                - 'hash': Perceptual hash (fastest)
                - 'pixel_diff': Mean pixel difference (fast)
                - 'structural_similarity': SSIM (most accurate)
        """
        self.algorithm = algorithm
    
    def compare(
        self,
        image1: bytes,
        image2: bytes,
        threshold: float = 0.95
    ) -> Tuple[bool, float]:
        """
        Compare two images.
        
        Args:
            image1: First image bytes (baseline)
            image2: Second image bytes (captured)
            threshold: Minimum similarity score to pass
            
        Returns:
            Tuple of (is_match, similarity_score)
        """
        if hashlib.sha256(image1).hexdigest() == hashlib.sha256(image2).hexdigest():
            return True, 1.0
        
        img1 = Image.open(io.BytesIO(image1)).convert('RGB')
        img2 = Image.open(io.BytesIO(image2)).convert('RGB')
        
        if img1.size != img2.size:
            img2 = img2.resize(img1.size, Image.Resampling.LANCZOS)
        
        if self.algorithm == 'hash':
            score = self._perceptual_hash_similarity(img1, img2)
        elif self.algorithm == 'pixel_diff':
            score = self._pixel_diff_similarity(img1, img2)
        else:
            score = self._ssim_similarity(img1, img2)
        
        return score >= threshold, score
    
    def _pixel_diff_similarity(
        self,
        img1: Image.Image,
        img2: Image.Image
    ) -> float:
        """Calculate similarity using mean pixel difference."""
        arr1 = np.array(img1, dtype=np.float32)
        arr2 = np.array(img2, dtype=np.float32)
        
        diff = np.abs(arr1 - arr2).mean() / 255.0
        return 1.0 - diff
    
    def _perceptual_hash_similarity(
        self,
        img1: Image.Image,
        img2: Image.Image,
        hash_size: int = 16
    ) -> float:
        """Calculate similarity using perceptual hashing."""
        def dhash(image: Image.Image) -> int:
            resized = image.resize((hash_size + 1, hash_size), Image.Resampling.LANCZOS)
            grayscale = resized.convert('L')
            pixels = np.array(grayscale)
            diff = pixels[:, 1:] > pixels[:, :-1]
            return int(np.packbits(diff.flatten()).tobytes().hex(), 16)
        
        hash1 = dhash(img1)
        hash2 = dhash(img2)
        
        xor = hash1 ^ hash2
        distance = bin(xor).count('1')
        max_distance = hash_size * hash_size
        
        return 1.0 - (distance / max_distance)
    
    def _ssim_similarity(
        self,
        img1: Image.Image,
        img2: Image.Image
    ) -> float:
        """Calculate Structural Similarity Index (SSIM)."""
        arr1 = np.array(img1.convert('L'), dtype=np.float64)
        arr2 = np.array(img2.convert('L'), dtype=np.float64)
        
        C1 = (0.01 * 255) ** 2
        C2 = (0.03 * 255) ** 2
        
        mu1 = arr1.mean()
        mu2 = arr2.mean()
        
        sigma1_sq = arr1.var()
        sigma2_sq = arr2.var()
        sigma12 = ((arr1 - mu1) * (arr2 - mu2)).mean()
        
        numerator = (2 * mu1 * mu2 + C1) * (2 * sigma12 + C2)
        denominator = (mu1**2 + mu2**2 + C1) * (sigma1_sq + sigma2_sq + C2)
        
        return float(numerator / denominator)


_comparator = None

def get_comparator(algorithm: str = 'structural_similarity') -> ImageComparator:
    """Get or create image comparator singleton."""
    global _comparator
    if _comparator is None or _comparator.algorithm != algorithm:
        _comparator = ImageComparator(algorithm)
    return _comparator


def quick_compare(
    baseline: bytes,
    captured: bytes,
    threshold: float = 0.95
) -> Tuple[bool, float]:
    """
    Quick comparison function.
    
    Returns:
        Tuple of (is_match, similarity_score)
    """
    return get_comparator().compare(baseline, captured, threshold)
