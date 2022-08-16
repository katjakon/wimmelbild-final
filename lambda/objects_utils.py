# -*- coding: utf-8 -*-
"""
Some functions to handle to hidden objects.
"""

import os
import json
import random

from hidden_object import HiddenObject
from hidden_picture import HiddenPicture


DESCRIPTION = "utils/description_utterances.json"
DESCRIPTION_VALUES = "utils/feature_values.json"
FEAT_FILE = "objects/features.json"
UTTERANCES = "utils/utterances.json"
OBJECTS = "utils/objects.json"


def get_objects(paths, directory=""):
    complete_objects = []
    for file in paths:
        file_path = os.path.join(directory, file)
        try:
            obj = HiddenObject.from_json(file_path, name=file)
            complete_objects.append(obj)
        except (TypeError, ValueError):
            continue
    return complete_objects


def get_features(path):
    with open(path, encoding="utf-8") as file:
        feats = json.load(file)
    return feats


def get_name(guess):
    names = get_features(OBJECTS)
    return names[guess.name]["name"]


def next_utterance(code, guess):
    utt_dict = get_features(UTTERANCES)
    if code == 1:
        return "Ist dein Objekt {}?".format(get_name(guess))
    elif code == 0:
        if guess is not None:
            return random.choice(utt_dict[guess])
    return random.choice(utt_dict["other_description"])


def generate_description(feature_value):
    # Choose filler utterance
    with open(os.path.join(UTTERANCES), encoding="utf-8") as utt_file:
        utt_dict = json.load(utt_file)
        filler = random.choice(utt_dict["filler"])
        i_know_sth = random.choice(utt_dict["i_know_sth"])
    with open(os.path.join(DESCRIPTION_VALUES), encoding="utf-8") as val_file:
        vals = json.load(val_file)
        feature, type, verbal = vals[feature_value]["feature"], vals[feature_value]["type"], vals[feature_value]["verbal"] 
    with open(os.path.join(DESCRIPTION), encoding="utf-8") as descr_file:
        descr_dict = json.load(descr_file)
        descr_templates = descr_dict[feature][type]
        # Choose random sentence
        descr_sent_template = random.choice(descr_templates)
        # Insert verbal element in to template
        description = descr_sent_template.format(verbal)
    return "{}, {}: {}.".format(filler, i_know_sth, description)


def choose_description(object, handler_input):
    attributes_manager = handler_input.attributes_manager
    # Choose random feature that should be described
    features = get_features(FEAT_FILE)
    value = None
    while value is None and features:
        descr_feat = random.choice(features)
        # Chose random value of that feature.
        value = object.get_feature_value(descr_feat)
        if value is None:
            features.remove(descr_feat)
    # Save chosen object
    attributes_manager.persistent_attributes["described_object"] = object.to_json_dict()
    attributes_manager.save_persistent_attributes()
    if not features:
        speak_output = "Mehr weiß ich leider nicht über mein Objekt."
    else:
        speak_output = generate_description(value)
    return speak_output
