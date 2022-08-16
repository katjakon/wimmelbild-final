from collections import defaultdict
import os

from hidden_object import HiddenObject

class HiddenPicture:

    def __init__(self, described, complete_obj):
        self.described = described
        self.complete_obj = complete_obj
        self.features = {feat for obj in self.complete_obj for feat in obj.feature_dict}
        self.asked = set()
        self.repeated = 0
        self.wrong = 0

    def add_description(self, feat, value):
        if value in self._poss_values(feat):
            self.described.feature_dict[feat].add(value)
            self.asked.add(feat)
            return True
        return False

    def add_asked(self, feat):
        self.asked.add(feat)

    def rank(self):
        sort = list(sorted(self.complete_obj, key= lambda x: self.described.compatibility(x), reverse=True))
        return [(obj, self.described.compatibility(obj)) for obj in sort]

    def distinctive_feat(self, objects):
        min_intersect = float("inf")
        feature = None
        for feat in self.features:
            if feat not in self.asked:
                vals = [obj.feature_dict[feat] for obj in objects]
                if vals:
                    intersection = set.intersection(*vals)
                    if len(intersection) < min_intersect:
                        min_intersect = len(intersection)
                        feature = feat
        return feature

    def filter(self, theta_abs=1, theta_rel=0.3):
        ranked = self.rank()
        candidates = []
        for obj, comp in ranked:
            absolute, relative = comp
            if absolute >= theta_abs and relative >= theta_rel:
                candidates.append(obj) 
        return candidates

    def next_action(self, theta_abs=1, theta_rel=0.2):
        candidates = self.filter(theta_abs, theta_rel)
        if 0 < len(candidates) <= 2:
            return 1, candidates[0]
        elif len(candidates) <= 4:
            return 0, self.distinctive_feat(candidates)
        return -1, None

    def _poss_values(self, feat):
        vals = set()
        for obj in self.complete_obj:
            vals.update(obj.feature_dict[feat])
        return vals

    def to_json_dict(self):
        json_dict = {}
        json_dict["described"] = self.described.json_serializable()
        json_dict["complete"] = [obj.name for obj in self.complete_obj]
        json_dict["features"] = list(self.features)
        json_dict["asked"] = list(self.asked)
        json_dict["repeated"] = self.repeated
        json_dict["wrong"] = self.wrong
        return json_dict

    @classmethod
    def from_json_dict(cls, json_dict, DIR=""):
        described = HiddenObject(json_dict["described"], name="described")
        completes = [HiddenObject.from_json(os.path.join(DIR, name), name=name) for name in json_dict["complete"]]
        pic = cls(described, completes)
        pic.repeated = json_dict["repeated"]
        pic.asked = set(json_dict["asked"])
        pic.wrong = int(json_dict["wrong"])
        return pic

if __name__ == "__main__":
    complete_objects = [HiddenObject.from_json(os.path.join("objects", name), name=name) for name in os.listdir("objects") if name != "features.json"]
    d = HiddenObject({"color": set(), "shape": {"rund"}}, name="described")
    for c in complete_objects:
        print(c.feature_dict)
    
    pic = HiddenPicture(d, complete_objects)
    print(pic.rank())
    code, guess = pic.next_action()
    print(code, guess)