import os 
import base64
from odoo.tools.mimetypes import guess_mimetype
from odoo import models, fields, api 
from PIL import Image

class ImageFilestore():

    def convert(self, p_id, binary_data, image_type):
        mimetype = guess_mimetype(base64.b64decode(binary_data))
        file_path = ""
        module_path = os.path.abspath(__file__).split('/')[:-2]
        img_dir_path = '/'.join(module_path)+'/images/'+image_type+'/'
        if mimetype == 'image/png':
            file_path = img_dir_path + str(p_id) + ".png"
        elif mimetype == 'image/jpeg':
            file_path = img_dir_path + str(p_id) + ".jpeg"
        if file_path:
            with open(file_path, "wb") as imgFile:
                imgFile.write(base64.b64decode(binary_data))
                img = Image.open(file_path)
                new_img = img.resize((512,300))
                new_img.save(file_path, "JPEG", optimize=True)
        return file_path

        # chmod -R a+rX *





