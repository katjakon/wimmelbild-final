# -*- coding: utf-8 -*-
"""
A class that represents an object in a hidden picture puzzle.
Objects can be compared with complete objects to assess compatability.
"""
from collections import defaultdict
import json
import random


class HiddenObject:

    def __init__(self, feature_dict, complete=False, name=""):
        if not isinstance(feature_dict, defaultdict):
            feature_dict = {feat: set(feature_dict[feat]) for feat in feature_dict}
            feature_dict = defaultdict(set, feature_dict)
        self.feature_dict = feature_dict
        self.complete = complete
        self.name = name
        # Possible descriptions for Alexa
        self.described = defaultdict(set, feature_dict)


    def get_feature_value(self, feature):
        """For given feature, return random value for this object.
        No value will be returned twice. If all values for given feature have been described, returns None.
        """
        values = self.described[feature]
        if not values:
            return None
        chosen_value = random.choice(list(values))
        # Delete chosen value from set of this feature so it can't be chosen twice.
        self.described[feature].remove(chosen_value)
        return chosen_value


    @classmethod
    def from_json(cls, file_path, complete=True, name=""):
        with open(file_path, encoding="utf-8") as json_f:
            feature_dict = json.load(json_f)
        # For efficient operations, convert values from lists to sets
        feature_dict = {feat: set(feature_dict[feat]) for feat in feature_dict}
        return cls(feature_dict, complete, name)

    def json_serializable(self):
        return {feat: list(self.feature_dict[feat]) for feat in self.feature_dict}

    def to_json_dict(self):
        return {
            "described": {feat: list(self.described[feat]) for feat in self.described},
            "features": {feat: list(self.feature_dict[feat]) for feat in self.feature_dict},
            "name": self.name

        }

    @classmethod
    def from_json_dict(cls, json_dict):
        instance =  cls(
            feature_dict = json_dict["features"],
            name = json_dict["name"]
        )
        instance.described = json_dict["described"]
        return instance


    def compatibility(self, complete_object, compatible_features=None):
        if compatible_features is None:
            compatible_features = []
        if not complete_object.complete:
            raise ValueError("HiddenObject needs to be complete to be compared.")
        comp_feats = 0
        n = 0
        for feature in complete_object.feature_dict:
            vals_complete = complete_object.feature_dict[feature]
            vals_self = self.feature_dict[feature]
            comp_feats += len(vals_complete.intersection(vals_self))
            n += len(vals_complete)
        return comp_feats, comp_feats/n

    def most_compatible(self, complete_objects):
        comp = 0
        comp_obj = []
        for obj in complete_objects:
            curr_comp = 0
            for feat in self.feature_dict:
                if self.feature_dict[feat].intersection(obj.feature_dict[feat]):
                    curr_comp += 1
            if curr_comp > comp:
                comp = curr_comp
                comp_obj = [obj]
            elif curr_comp == comp:
                comp_obj.append(obj)
        return comp_obj

    def rank(self, complete_objects):
        return sorted(complete_objects, key=lambda x: self.compatibility(x), reverse=True)

    def filter(self, threshold, complete_objects):
        return list(filter(lambda x: self.compatibility(x) > threshold, complete_objects))

    def distinctive_feat(self, complete_objects, features):
        min_intersect = float("inf")
        feature = None
        for feat in features:
            vals = (obj.feature_dict[feat] for obj in complete_objects)
            if vals:
                intersection = set.intersection(*vals)
                if len(intersection) < min_intersect:
                    min_intersect = len(intersection)
                    feature = feat
        return feature

    def __str__(self):
        return "<HiddenObject '{}' with features: {}>".format(self.name, str(dict(self.feature_dict)))

    def __repr__(self):
        return "<HiddenObject '{}'>".format(self.name)

