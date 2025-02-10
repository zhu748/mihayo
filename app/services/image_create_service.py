import time
import uuid

from google import genai
from google.genai import types
import base64

from app.core.config import settings
from app.core.logger import get_image_create_logger
from app.core.uploader import ImageUploaderFactory
from app.schemas.openai_models import ImageGenerationRequest

logger = get_image_create_logger()


class ImageCreateService:
    def __init__(self, aspect_ratio="1:1"):
        self.image_model = settings.CREATE_IMAGE_MODEL
        self.paid_key = settings.PAID_KEY
        self.aspect_ratio = aspect_ratio

    def generate_images(self, request: ImageGenerationRequest):
        client = genai.Client(api_key=self.paid_key)
        if request.size == "1024x1024":
            self.aspect_ratio = "1:1"
        elif request.size == "1792x1024":
            self.aspect_ratio = "16:9"
        elif request.size == "1027x1792":
            self.aspect_ratio = "9:16"
        else:
            raise ValueError(
                f"Invalid size: {request.size}. Supported sizes are 1024x1024, 1792x1024, and 1024x1792."
            )

        response = client.models.generate_images(
            model=self.image_model,
            prompt=request.prompt,
            config=types.GenerateImagesConfig(
                number_of_images=request.n,
                output_mime_type="image/png",
                aspect_ratio=self.aspect_ratio,
                safety_filter_level="BLOCK_LOW_AND_ABOVE",
                person_generation="ALLOW_ADULT",
                # language="auto"
            ),
        )

        if response.generated_images:
            images_data = []
            for index, generated_image in enumerate(response.generated_images):
                image_data = generated_image.image.image_bytes
                image_uploader = None
                if settings.UPLOAD_PROVIDER  == "smms":
                    image_uploader = ImageUploaderFactory.create(provider=settings.UPLOAD_PROVIDER,api_key=settings.SMMS_SECRET_TOKEN)
                    current_date = time.strftime("%Y/%m/%d")
                    filename = f"{current_date}/{uuid.uuid4().hex[:8]}.png"
                    upload_response = image_uploader.upload(image_data,filename)
                    
                if request.response_format == "b64_json":
                    base64_image = base64.b64encode(image_data).decode('utf-8')
                    images_data.append({
                        "b64_json": base64_image,
                        "revised_prompt": request.prompt
                    })
                else:
                    images_data.append({
                        "url": f"{upload_response.data.url}",
                        "revised_prompt": request.prompt
                    })

            response_data = {
                "created": int(time.time()),  # Current timestamp
                "data": images_data
            }
            return response_data
        else:
            raise Exception("I can't generate these images")

    def generate_images_chat(self, request: ImageGenerationRequest) -> str:
        response = self.generate_images(request)
        image_datas = response["data"]
        if image_datas:
            markdown_images = []
            for index, image_data in enumerate(image_datas):
                if 'url' in image_data:
                    markdown_images.append(f"![Generated Image {index+1}]({image_data['url']})")
                else:
                    # 如果是base64格式，创建data URL
                    markdown_images.append(f"![Generated Image {index+1}](data:image/png;base64,{image_data['b64_json']})")
            return "\n".join(markdown_images)
