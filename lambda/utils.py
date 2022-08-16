# -*- coding: utf-8 -*-
"""
Util functions
"""

import json
import logging
import os
import boto3
from botocore.exceptions import ClientError


def create_presigned_url(object_name):
    """Generate a presigned URL to share an S3 object with a capped expiration of 60 seconds

    :param object_name: string
    :return: Presigned URL as string. If error, returns None.
    """
    s3_client = boto3.client('s3',
                             region_name=os.environ.get('S3_PERSISTENCE_REGION'),
                             config=boto3.session.Config(signature_version='s3v4',s3={'addressing_style': 'path'}))
    try:
        bucket_name = os.environ.get('S3_PERSISTENCE_BUCKET')
        response = s3_client.generate_presigned_url('get_object',
                                                    Params={'Bucket': bucket_name,
                                                            'Key': object_name},
                                                    ExpiresIn=60*5)
    except ClientError as e:
        logging.error(e)
        return None

    # The response contains the presigned URL
    return response


# Eigene Hilfsfunktionen
def load_apl_document(file_path):
    """Load the apl json document from given path as a dict object."""
    with open(file_path) as f:
        return json.load(f)


def load_txt(file_path):
    """Read in a text from a file."""
    with open(file_path) as f:
        return f.read()


def get_filled_slot_values(slots):
    """Get filled slot values."""
    if slots is None:
        return None
    values = []
    for slot_name in slots:
        value = slots[slot_name].value
        if value is not None:
            values.append(value)
    if not values:
        return None
    return values
