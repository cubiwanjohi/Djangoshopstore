import cloudinary.uploader
from cloudinary.utils import cloudinary_url
from django.core.files.storage import Storage


class CloudinaryMediaStorage(Storage):
    """Store uploaded ShopStore images in Cloudinary."""

    def _save(self, name, content):
        result = cloudinary.uploader.upload(
            content,
            folder="shopstore/products",
            use_filename=True,
            unique_filename=True,
            overwrite=False,
            resource_type="image",
        )
        return result["public_id"]

    def exists(self, name):
        # Cloudinary generates unique filenames for uploaded images.
        return False

    def url(self, name):
        image_url, _ = cloudinary_url(
            name,
            secure=True,
            resource_type="image",
        )
        return image_url

    def delete(self, name):
        cloudinary.uploader.destroy(
            name,
            resource_type="image",
        )
