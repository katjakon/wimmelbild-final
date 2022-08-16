# -*- coding: utf-8 -*-

# A skill that lets you play a game with Alexa
import logging
import os
import random
import ask_sdk_core.utils as ask_utils

from ask_sdk_core.skill_builder import CustomSkillBuilder
from ask_sdk_core.dispatch_components import AbstractRequestHandler
from ask_sdk_core.dispatch_components import AbstractExceptionHandler
from ask_sdk_core.handler_input import HandlerInput

from ask_sdk_model import Response
from ask_sdk_model.interfaces.alexa.presentation.apl import (
    RenderDocumentDirective, ExecuteCommandsDirective, SpeakItemCommand,
    AutoPageCommand, HighlightMode)
from ask_sdk_model.interfaces.alexa.presentation.apl import UserEvent
from ask_sdk_core.utils import (
    is_intent_name, get_supported_interfaces, get_slot, get_slot_value)

from hidden_object import HiddenObject
from hidden_picture import HiddenPicture
from utils import create_presigned_url, load_apl_document, load_txt, get_filled_slot_values
from objects_utils import get_objects, get_features, next_utterance, get_name, generate_description, choose_description

from ask_sdk_s3.adapter import S3Adapter
s3_adapter = S3Adapter(bucket_name=os.environ["S3_PERSISTENCE_BUCKET"])


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


OBJ_DIR = "objects/"
UTTERANCES = "utils/utterances.json"
OBJ_MAPPING_FILE = "utils/objects.json"
# APL and data documents
HIDDENOBJECT_TOUCH_APL = "visuals/hiddenobject_touch_apl.json"
HIDDENOBJECT_NOTOUCH_APL = "visuals/hiddenobject_apl.json"
HIDDENOBJECT_OPTIONS_APL = "visuals/hiddenobject_options_apl.json"
HOMESCREEN_APL = "visuals/homescreen_apl.json"
HOMESCREEN_DATA = "visuals/homescreen_data.json"
PROGRAMSTRUCTURE_APL = "visuals/program_structure_apl.json"
PROGRAMSTRUCTURE_DATA = "visuals/program_structure_data.json"
PLACE_APL = "visuals/place_apl.json"
PLACE_DATA = "visuals/place_data.json"
STUDYINFOMAIN_APL = "visuals/study_info_main.json"
STUDYINFOMAIN_DATA = "visuals/study_info_main_data.json"
GENERALSTUDYINFO_APL = "visuals/general_study_info_apl.json"
PAGER_APL = "visuals/general_study_info/pager_apl.json"
PAGER_MAPPING = {
    "immatrikulation": "visuals/general_study_info/immatrikulation_data.json",
    "housing": "visuals/general_study_info/housing_data.json",
    "finanzen": "visuals/general_study_info/money_data.json",
    "freetime": "visuals/general_study_info/freetime_data.json",
    "laufbahn": "visuals/general_study_info/university_data.json",
    "learning": "visuals/general_study_info/learning_data.json"
}


class LaunchRequestHandler(AbstractRequestHandler):
    """Handler for Skill Launch."""

    def can_handle(self, handler_input):
        # Can handle if user starts skill via invocation
        return ask_utils.is_request_type("LaunchRequest")(handler_input)

    def handle(self, handler_input):
        """Direct to the HomeScreenIntentHandler with a new round."""
        # Delete persistent_attributes from previous sessions for fresh start!
        attributes_manager = handler_input.attributes_manager
        attributes_manager.delete_persistent_attributes()
        # welcome will be uttered before the usual HomeScreenIntentHandler speak output
        welcome = "Herzlich willkommen zum großen Wimmelbild-Spaß!"
        return HomeScreenIntentHandler().handle(handler_input, welcome)


class HomeScreenIntentHandler(AbstractRequestHandler):
    """Handler for home screen with ame mode options."""

    def can_handle(self, handler_input):
        # Can handle if user utters wish to go to home screen
        # ...or directed from TouchIntentHandler
        return ask_utils.is_intent_name("HomeScreenIntent")(handler_input)

    def handle(self, handler_input, welcome=""):
        """Allow user to choose game mode or expanation."""
        speak_output = welcome + " Hier bist du im Menü. Was möchtest du als nächstes tun?"
        # Return homescreen visuals and concatenated speak_output
        return handler_input.response_builder.speak(speak_output).add_directive(
            RenderDocumentDirective(
                document=load_apl_document(HOMESCREEN_APL),
                datasources=load_apl_document(HOMESCREEN_DATA)
            )
        ).ask("Du kannst eine Auswahl treffen.").response


class ExplanationIntentHandler(AbstractRequestHandler):
    """Handler for intent with explanation of game."""
    def can_handle(self, handler_input):
        # Can handle if user utters wish to hear the explanation
        # ...or directed from TouchIntentHandler (user chose explanation via touch in home screen)
        return ask_utils.is_intent_name("ExplanationIntent")(handler_input)

    def handle(self, handler_input):
        """Explain the game to the user."""
        # Prepare visuals
        apl_doc = load_apl_document(HIDDENOBJECT_OPTIONS_APL)
        data_doc = load_apl_document(STUDYINFOMAIN_DATA)
        data_doc["wimmelbild"]["images"]["options"] = create_presigned_url(data_doc["wimmelbild"]["images"]["options"])
        data_doc["wimmelbild"]["choice"] = "options"
        # Prepare speak outpus
        speak_output = ("Bei einem Wimmelbild-Spiel geht es darum, Objekte in einem Bild zu finden. "
                        "Dieses Spiel hier soll aber noch mehr können: "
                        "Es soll spielerisch Informationen zu verschiedenen Studienfächern vermitteln. "
                        "Im Bild siehst du die Objekte, die in diesem Spiel verfügbar sind. "
                        "Es gibt zwei Spielarten: "
                        "Ich beschreibe und du versuchst das Objekt zu erraten oder "
                        "Du beschreibst mir ein Objekt und ich versuche es zu erraten. "
                        "Dabei kannst du zum Beispiel Form und Farbe des Objektes verwenden, "
                        "nicht aber den Namen oder eine direkte Bezeichnung. "
                        "Wenn das Objekt erraten wurde, dann erzähle ich dir noch ein wenig "
                        "über ein dazu passendes Studienfach. "
                        "Wenn du magst, kannst du danach das Spiel erneut starten")

        return handler_input.response_builder.speak(speak_output).add_directive(
            RenderDocumentDirective(
                document=apl_doc,
                datasources=data_doc
            )
        ).response


class TouchIntentHandler(AbstractRequestHandler):
    """Handler for Hello World Intent."""

    def can_handle(self, handler_input):
        # Can handle if user has touched a touchable component on the screen
        request = handler_input.request_envelope.request
        if isinstance(request, UserEvent):
            # return true for userEvent request with at least 1 argument
            return len(request.arguments) > 0
        return False

    def handle(self, handler_input):
        """Direct to the right handler based on which component has been touched."""
        req = handler_input.request_envelope.request
        user_choice = req.arguments[0]
        attributes_manager = handler_input.attributes_manager
        logging.info(print("you chose:", user_choice))
        logging.info(print("Send Event rumkommt: ", req))
        objects = {"mathe.json", "planet.json", "chemie.json", "fff.json", "birne.json", "globe.json", "abc.json", "virus.json",
                   "binary.json", "biene.json", "tafel.json", "doktor.json", "ordner.json", "zimmerpflanze.json", "balloon.json", "europa.json",
                   "telescope.json", "column.json", "helloworld.json", "boot.json"}
        if user_choice == "game":
            return HiddenObjectIntentHandler().handle(handler_input)
        elif user_choice == "game2":
            return StartOtherDirectionIntent().handle(handler_input)
        elif user_choice == "explanation":
            return ExplanationIntentHandler().handle(handler_input)
        elif user_choice == "goBacktoHomescreen":
            return HomeScreenIntentHandler().handle(handler_input)
        elif user_choice == "Aufbau":
            return ProgramStructureIntentHandler().handle(handler_input)
        elif user_choice == "backToInfo":
            return StudyInfoIntendHandler().handle(handler_input, mount=False)
        elif user_choice == "Ort":
            return StudyPlaceSuggestionIntentHandler().handle(handler_input)
        elif user_choice == "backToGame":
            return HomeScreenIntentHandler().handle(handler_input)
        elif user_choice == "end":
            return CancelOrStopIntentHandler().handle(handler_input)
        elif user_choice == "goBack":
            return HomeScreenIntentHandler().handle(handler_input)
        elif user_choice == "backToAllg":
            return GeneralStudyInfoIntendHandler().handle(handler_input)
        elif user_choice == "allg":
            return PagerInfoIntendHandler().handle(handler_input, req.arguments[1])
        elif user_choice in objects:
            return IsThatItIntentHandler().handle(handler_input, user_choice)
        return (
            handler_input.response_builder
                .speak("Nun ja, irgendwie sitze ich hier und weiß nicht, wie ich hier hingekommen bin.")
                # .ask("add a reprompt if you want to keep the session open for the user to respond")
                .response
        )

class HiddenObjectIntentHandler(AbstractRequestHandler):
    """Handler for Intent for game mode 1 (user describes)."""

    def can_handle(self, handler_input):
        # Can handle if user utters wish to start this game mode
        # ...or directed from TouchIntentHandler (user chose game mode via touch in home screen)
        return ask_utils.is_intent_name("HiddenObjectIntent")(handler_input)

    def handle(self, handler_input):
        """Show objects and tell user to start describing."""
        # Start new game and load all complete objects
        complete_objects = get_objects(os.listdir(OBJ_DIR), OBJ_DIR)
        pic = HiddenPicture(HiddenObject({}, name="described"), complete_objects)
        json_dict = pic.to_json_dict()
        attributes_manager = handler_input.attributes_manager
        attributes_manager.persistent_attributes.update(json_dict)

        # Set game mode:
        attributes_manager.persistent_attributes["game_mode"] = "user_describes"
        attributes_manager.save_persistent_attributes()

        # Prepare visuals and speak_output
        speak_output = "Dann such dir mal ein Objekt aus und gib mir Hinweise dazu. Aber mach es mir nicht zu einfach - am besten nur eine Eigenschaft pro Hinweis! Übrigens: Wenn du auf die Glühbirne unten links klickst, siehst du alle verfügbaren Objekte."
        apl_doc = load_apl_document(HIDDENOBJECT_NOTOUCH_APL)
        data_doc = load_apl_document(STUDYINFOMAIN_DATA)
        data_doc["hiddenObjectsImage"]["highlightObjectsOn"] = create_presigned_url(data_doc["hiddenObjectsImage"]["highlightObjectsOn"])
        data_doc["hiddenObjectsImage"]["highlightObjectsOff"] = create_presigned_url(data_doc["hiddenObjectsImage"]["highlightObjectsOff"])

        # Save state
        attributes_manager.persistent_attributes["state"] = "hidden_object"
        attributes_manager.save_persistent_attributes()
        return (
            handler_input.response_builder
                .speak(speak_output)
                .ask("Gib mir einen Hinweis zu deinem Objekt.")
                .add_directive(
                    RenderDocumentDirective(
                        document=apl_doc,
                        datasources=data_doc
                    )
                )
                .response
        )


class StartOtherDirectionIntent(AbstractRequestHandler):
    """Handler for starting "Alexa describes" direction game mode (mode 2)."""

    def can_handle(self, handler_input):
        # Can handle if user utters wish to start this game mode
        # ...or directed from TouchIntentHandler (user chose game mode via touch in home screen)
        return ask_utils.is_intent_name("StartOtherDirectionIntent")(handler_input)

    def handle(self, handler_input):
        """Ask user about favorite school subject and initialize game params."""
        # Start new game and load all complete objects
        speak_output = "Ok, dann werde ich dir jetzt ein Objekt beschreiben. Ich kann mich aber noch gar nicht entscheiden, welches am besten. Vielleicht kannst du mir da helfen: Was ist denn dein Lieblingsschulfach?"
        # Get visuals
        apl_doc = load_apl_document(HIDDENOBJECT_NOTOUCH_APL)
        data_doc = load_apl_document(STUDYINFOMAIN_DATA)
        data_doc["hiddenObjectsImage"]["highlightObjectsOn"] = create_presigned_url(data_doc["hiddenObjectsImage"]["highlightObjectsOn"])
        data_doc["hiddenObjectsImage"]["highlightObjectsOff"] = create_presigned_url(data_doc["hiddenObjectsImage"]["highlightObjectsOff"])
        handler_input.response_builder.add_directive(
            RenderDocumentDirective(
                document=apl_doc,
                datasources=data_doc
            )
        )
        # Save state and initialize game parameters
        attributes_manager = handler_input.attributes_manager
        complete_objects = get_objects(os.listdir(OBJ_DIR), OBJ_DIR)
        attributes_manager = handler_input.attributes_manager
        attributes_manager.persistent_attributes["tries"] = 0
        attributes_manager.persistent_attributes["game_mode"] = "alexa_describes"
        attributes_manager.persistent_attributes["state"] = "other_direction"
        attributes_manager.save_persistent_attributes()
        attributes_manager.save_persistent_attributes()
        return (
            handler_input.response_builder
                .speak(speak_output)
                .ask("Welches Schulfach magst du am liebsten?")
                .response
        )


class ChooseWordIntentHandler(AbstractRequestHandler):
    """Handler for Hello World Intent."""

    def can_handle(self, handler_input):
        # Can handle if user choose school subject
        # ...and previous state is other_direction
        attributes_manager = handler_input.attributes_manager
        return ask_utils.is_intent_name("ChooseWordIntent")(handler_input) and attributes_manager.persistent_attributes["state"] == "other_direction"

    def handle(self, handler_input):
        """Ask user to choose a word (out of Hintergrund, Auswirkung and Anwendung)."""
        # Start new game and load all complete objects
        slots = handler_input.request_envelope.request.intent.slots
        # Get subject
        subj = slots["schoolsubj"].resolutions.resolutions_per_authority[0].values[0].value.id
        # Save
        attributes_manager = handler_input.attributes_manager
        attributes_manager.persistent_attributes["state"] = "choose_word"
        attributes_manager.persistent_attributes["personality"] = {"subj": subj}  #slots["schoolsubj"].value.id}
        attributes_manager.save_persistent_attributes()
        # Ask user to choose a word
        speak_output = "Alles klar, ist notiert. Dann wähle jetzt einen dieser drei Begriffe: Hintergrund, Anwendung oder Auswirkung?"
        return (
            handler_input.response_builder
                .speak(speak_output)
                .ask("Du musst eine Auswahl treffen.")
                .response
        )


class ChooseObjectIntentHandler(AbstractRequestHandler):
    """Handle user choice of word, start with game for selected object."""

    def can_handle(self, handler_input):
        # Can handle if user uttered one of the three options
        # Auswirkung, Hintergrund, Anwendung
        # ...and previous state is choose_word
        # ...or: directed from DontKnowIntentHandler
        attributes_manager = handler_input.attributes_manager
        return ask_utils.is_intent_name("ChooseObjectIntent")(handler_input) and attributes_manager.persistent_attributes["state"] == "choose_word"

    def handle(self, handler_input):
        """Select object based on user's answers and start game."""
        # Start new game and load all complete objects
        attributes_manager = handler_input.attributes_manager
        slots = handler_input.request_envelope.request.intent.slots
        word_choice = ""
        logging.info(print("word choice:", slots))
        # get choices
        personality = attributes_manager.persistent_attributes.get("personality")
        if personality is not None:
            subj = personality["subj"]
        if slots:
            word_choice = slots.get("choice", "")
        if word_choice:
            word_choice = word_choice.value
        obj_dict = load_apl_document("utils/choose_object.json")
        if word_choice.lower() == "hintergrund":
            obj_choice = obj_dict[subj][0]
        elif word_choice.lower() == "anwendung":
            obj_choice = obj_dict[subj][1]
        elif word_choice.lower() == "auswirkung":
            obj_choice = obj_dict[subj][2]
        else:
            obj_choice = "doktor.json"
        # Set state.
        attributes_manager.persistent_attributes["state"] = "choose_object"
        attributes_manager.save_persistent_attributes()
        
        # Get all available objects
        complete_objects = get_objects(os.listdir(OBJ_DIR), OBJ_DIR)
        
        # Iterate over them to find chosen object. Default is the doctor
        descr_obj = "doktor.json"
        for obj in complete_objects:
            if obj.name == obj_choice:
                descr_obj = obj
        
        # Generate description for chosen object
        speak_output = choose_description(descr_obj, handler_input) + " Denk daran, dass du immer nach mehr Informationen fragen kannst. Wenn du auf die Glühbirne unten links klickst, siehst du alle verfügbaren Objekte."
        logging.info(print("Chosen object for description", get_name(descr_obj)))
        logging.info(print(attributes_manager.persistent_attributes["state"]))
        
        # Get and display visuals
        apl_doc = load_apl_document(HIDDENOBJECT_TOUCH_APL)
        data_doc = load_apl_document(STUDYINFOMAIN_DATA)
        data_doc["hiddenObjectsImage"]["highlightObjectsOn"] = create_presigned_url(data_doc["hiddenObjectsImage"]["highlightObjectsOn"])
        data_doc["hiddenObjectsImage"]["highlightObjectsOff"] = create_presigned_url(data_doc["hiddenObjectsImage"]["highlightObjectsOff"])
        handler_input.response_builder.add_directive(
            RenderDocumentDirective(
                document=apl_doc,
                datasources=data_doc
            )
        )
        return (
            handler_input.response_builder
                .speak(speak_output)
                .ask(speak_output)
                .response )


class DescriptionIntentHandler(AbstractRequestHandler):
    """Handle user provviding description of object."""

    def can_handle(self, handler_input):
        # Can handle if user provided description of object
        return ask_utils.is_intent_name("DescriptionIntent")(handler_input)

    def handle(self, handler_input):
        """Process description provided by user, possibly make a guess."""
        attributes_manager = handler_input.attributes_manager
        mode = attributes_manager.persistent_attributes.get("game_mode")
        if mode == "alexa_describes":
            return MoreIntentHandler().handle(handler_input)
        elif mode is None:
            return HomeScreenIntentHandler().handle(handler_input, welcome="Oh, irgendwas ist falsch gelaufen...")
        pic = HiddenPicture.from_json_dict(attributes_manager.persistent_attributes, OBJ_DIR)
        features = attributes_manager.persistent_attributes["features"]

        # Add any features that were described to object
        slots = handler_input.request_envelope.request.intent.slots
        logging.info(print(get_filled_slot_values(slots)))
        #logging.info(print(attributes_manager.persistent_attributes))
        for feat in features:
            if slots is not None and slots[feat].value is not None:
                # Use id to avoid to many similar descriptions in complete objects.
                try:
                    slot_id = slots[feat].resolutions.resolutions_per_authority[0].values[0].value.id
                # For inbuilt slots there seem to be no id.
                except (AttributeError, TypeError):
                    slot_id = slots[feat].value
                    logging.info(print("Failed Feature", feat))
                logging.info(print("Feature:", feat, "Value:", slots[feat].value, "ID:", slot_id))
                pic.add_description(feat, slot_id)
                pic.add_asked(feat)
        
        # Choose next action
        code, guess = pic.next_action()
        speak_output = next_utterance(code, guess)

        logging.info(print("Code and Guess", code, guess))
        logging.info(print("Ranking", pic.rank()))
        logging.info(print(pic.described))
        logging.info(print("Asked", pic.asked))

        # There is a distinctive feature
        if code == 0 and guess is not None:
            attributes_manager.persistent_attributes["question"] = True
            # Add distinctive feature to asked
            pic.add_asked(guess)

        # There is no distinctive feature and no probable guess
        if code == -1 or guess is None:
            pic.repeated += 1

        # There has been to many repition -- time out: make best guess
        if pic.repeated >= 2:
            guess = pic.rank()[0][0]
            speak_output = next_utterance(1, guess)

        # There is a best guess
        if isinstance(guess, HiddenObject):
            attributes_manager.persistent_attributes["guess"] = [guess.json_serializable(), guess.name]
            attributes_manager.persistent_attributes["last-state-guess"] = True
            # Display correct image
            logging.info(print("Image Name", guess.name))
            apl_doc = load_apl_document(HIDDENOBJECT_OPTIONS_APL)
            data_doc = load_apl_document(STUDYINFOMAIN_DATA)
            data_doc["wimmelbild"]["images"][guess.name] = create_presigned_url(data_doc["wimmelbild"]["images"][guess.name])
            data_doc["wimmelbild"]["choice"] = guess.name
            handler_input.response_builder.add_directive(
                RenderDocumentDirective(
                    document=apl_doc,
                    datasources=data_doc
                )
            )
        json_dict = pic.to_json_dict()
        logging.info(print("JSON DICT", json_dict))
        attributes_manager.persistent_attributes.update(json_dict)
        # Set state
        attributes_manager.persistent_attributes["state"] = "description"
        attributes_manager.save_persistent_attributes()
        logging.info(print(attributes_manager.persistent_attributes["state"]))
        return (
            handler_input.response_builder
                .speak(speak_output)
                .ask(speak_output)
                .response
        )

    
class DontKnowIntentHandler(AbstractRequestHandler):
    """Handle user expressing confusion or uncertainty."""

    def can_handle(self, handler_input):
        # Can handle if user uttered satement of uncertainty or confusion
        return ask_utils.is_intent_name("DontKnowIntent")(handler_input)

    def handle(self, handler_input):
        """Prepare answer according to previous state."""
        attributes_manager = handler_input.attributes_manager
        previous_state = attributes_manager.persistent_attributes.get("state")
        # Direct to other handlers based on previous states
        if previous_state in {"more", "choose_object"}:
            return MoreIntentHandler().handle(handler_input)
        elif previous_state in {"other_direction", "choose_word"}:
            return ChooseObjectIntentHandler().handle(handler_input)
        elif previous_state == "hidden_object":
            # We can probably do this in a more elegant manner (Making sure the question has not been asked before!)
            speak_output = "Sag mir doch noch mehr zur Farbe oder Position deines Objekts."
            return (
                handler_input.response_builder
                    .speak(speak_output)
                    .ask("Gib mir einen Hinweis zu deinem Objekt.")
                    .response
            )
        # User does not have any further description, make guess with highest ranked object
        attributes_manager.persistent_attributes["state"] = "dont_know"
        pic = HiddenPicture.from_json_dict(attributes_manager.persistent_attributes, OBJ_DIR)

        if "question" in attributes_manager.persistent_attributes and attributes_manager.persistent_attributes["question"] is True:
            attributes_manager.persistent_attributes["question"] = False
            attributes_manager.save_persistent_attributes()
            return DescriptionIntentHandler().handle(handler_input)
        guess = pic.rank()[0][0]

        attributes_manager.persistent_attributes["guess"] = [guess.json_serializable(), guess.name]
        attributes_manager.save_persistent_attributes()

        apl_doc = load_apl_document(HIDDENOBJECT_OPTIONS_APL)
        data_doc = load_apl_document(STUDYINFOMAIN_DATA)
        data_doc["wimmelbild"]["images"][guess.name] = create_presigned_url(data_doc["wimmelbild"]["images"][guess.name])
        data_doc["wimmelbild"]["choice"] = guess.name
        handler_input.response_builder.add_directive(
                RenderDocumentDirective(
                    document=apl_doc,
                    datasources=data_doc
                )
            )
        name = get_name(guess)
        speak_output = "Okay, ich versuch's trotzdem mal. Ist dein Objekt {}?".format(name)
        logging.info(print(attributes_manager.persistent_attributes["state"]))
        return (
            handler_input.response_builder
                .speak(speak_output)
                .ask(speak_output)
                .response
        )


class ProgramStructureIntentHandler(AbstractRequestHandler):
    """Handle provision of info about a subject."""

    def can_handle(self, handler_input):
        # Always false: can only handle if directed to in previous state
        return False

    def handle(self, handler_input):
        """Display correct info text."""
        attributes_manager = handler_input.attributes_manager
        # Retrieve current object
        if attributes_manager.persistent_attributes["game_mode"] == "user_describes":
            selected_object = attributes_manager.persistent_attributes["guess"][-1]
        else:
            selected_object = attributes_manager.persistent_attributes["described_object"]["name"]
        json_dict = get_features(OBJ_MAPPING_FILE)
        # Get text
        txt_file = json_dict[selected_object]["txt_file"]
        text = load_txt(txt_file)
        # Prepare visuals with text
        apl_doc = load_apl_document(PROGRAMSTRUCTURE_APL)
        data_doc = load_apl_document(PROGRAMSTRUCTURE_DATA)
        data_doc["subjects"]["text"] = text
        handler_input.response_builder.add_directive(
            RenderDocumentDirective(
                document=apl_doc,
                datasources=data_doc
            )
        )
        # Add speak_output
        speak_output = "Hier findest du Infos zum Aufbau."
        return (
            handler_input.response_builder
                .speak(speak_output)
                .response
        )


class StudyPlaceSuggestionIntentHandler(AbstractRequestHandler):
    """Handle suggestion of study place"""

    def can_handle(self, handler_input):
        # Always false: can only handle if directed to in previous state
        return False

    def handle(self, handler_input):
        """Randomly choose place and oresent it to the user."""
        attributes_manager = handler_input.attributes_manager
        # Retrieve current object
        if attributes_manager.persistent_attributes["game_mode"] == "user_describes":
            selected_object = attributes_manager.persistent_attributes["guess"][-1]
        else:
            selected_object = attributes_manager.persistent_attributes["described_object"]["name"]
        # Get visuals for place
        apl_doc = load_apl_document(PLACE_APL)
        data_doc = load_apl_document(PLACE_DATA)
        place = random.choice(data_doc["cities"][selected_object])
        data_doc["cities"]["choice"] = place
        speak_output = "Wie wäre es mit einem Studium in {}?".format(place)
        handler_input.response_builder.add_directive(
            RenderDocumentDirective(
                document=apl_doc,
                datasources=data_doc
            )
        )
        return (
            handler_input.response_builder
                .speak(speak_output)
                .response
        )


class StudyInfoIntendHandler(AbstractRequestHandler):
    """Handle provision of info about study subject."""

    def can_handle(self, handler_input):
        # Always false: can only handle if directed to in previous state
        return False

    def handle(self, handler_input, mount=True, show_obj=False):
        """Display info about a subject after object has been guessed correctly."""
        attributes_manager = handler_input.attributes_manager
        if attributes_manager.persistent_attributes["game_mode"] == "user_describes":
            selected_object = attributes_manager.persistent_attributes["guess"][-1]
        else:
            selected_object = attributes_manager.persistent_attributes["described_object"]["name"]
        json_dict = get_features(OBJ_MAPPING_FILE)
        # Prepare visuals
        apl_doc = load_apl_document(STUDYINFOMAIN_APL)
        data_doc = load_apl_document(STUDYINFOMAIN_DATA)
        data_doc["wimmelbild"]["choice"] = selected_object
        if mount:
            subj_name = data_doc["fachData"]["subject"][selected_object]
            speak_output = "Super! Dazu habe ich dir das Studienfach {} rausgesucht. Hier siehst du die Infos. Sieh dich in Ruhe um. Sag mir Bescheid, wenn du noch eine Runde spielen möchtest.".format(subj_name)
        else:
            speak_output = "Hier siehst du die Infos."
        # Prepare timer 
        if show_obj:
            # Make sure correct image can be shown
            data_doc["wimmelbild"]["images"][selected_object] = create_presigned_url(data_doc["wimmelbild"]["images"][selected_object])
        else:
            # Set timerDuration to 0 to not show the object
            data_doc["timerData"]["timerDuration"] = 0
        # Add visuals to return directives
        handler_input.response_builder.add_directive(
            RenderDocumentDirective(
                document=apl_doc,
                datasources=data_doc
            )
        )
        return (
            handler_input.response_builder
                .speak(speak_output)
                .response
        )


class GeneralStudyInfoIntendHandler(AbstractRequestHandler):
    """Show some general info obout studying."""

    def can_handle(self, handler_input):
        # Always false: can only handle if directed to in previous state
        return False

    def handle(self, handler_input, arrive=False, show_obj=False):
        apl_doc = load_apl_document(GENERALSTUDYINFO_APL)
        data_doc = load_apl_document(STUDYINFOMAIN_DATA)
        # Prepare data_doc to correctly display visuals and speak_output
        speak_output = "Hier findest du eine allgemeine Zusammenstellung zum Thema Studium"
        if show_obj:
            # Make sure doctor image can be shown
            data_doc["wimmelbild"]["images"]["doktor.json"] = create_presigned_url(data_doc["wimmelbild"]["images"]["doktor.json"])
            data_doc["timerData"]["timerDuration"] = 3000
            speak_output = "Genau! Es war der Doktor. " + speak_output
        else:
            # Set timerDuration to 0 to not show the object
            data_doc["timerData"]["timerDuration"] = 0
        # Add visuals to return directives
        handler_input.response_builder.add_directive(
            RenderDocumentDirective(
                document=apl_doc,
                datasources=data_doc
            )
        )
        # Only add speak_output if arriving in info menu for the first time
        if arrive:
            return (
                handler_input.response_builder
                    .speak(speak_output)
                    .response
            )
        else:
            return (
                handler_input.response_builder
                    .response
            )


class PagerInfoIntendHandler(AbstractRequestHandler):
    """Display general study info via pagers."""

    def can_handle(self, handler_input):
        # Always false: can only handle if directed to in previous state
        return False

    def handle(self, handler_input, choice):
        # load correct visuals
        apl_doc = load_apl_document(PAGER_APL)
        data_doc = load_apl_document(PAGER_MAPPING[choice])
        handler_input.response_builder.add_directive(
            RenderDocumentDirective(
                document=apl_doc,
                datasources=data_doc
            )
        )
        return (
            handler_input.response_builder
                .response
        )


class YesIntentHandler(AbstractRequestHandler):
    """Handler for affirming statements."""

    def can_handle(self, handler_input):
        # Can handle if user said yes or something similar
        return ask_utils.is_intent_name("AMAZON.YesIntent")(handler_input)

    def handle(self, handler_input):
        """Handle "yes" answer in accorddance with previous state."""
        attributes_manager = handler_input.attributes_manager
        if "last-state-guess" in attributes_manager.persistent_attributes and attributes_manager.persistent_attributes["last-state-guess"] is True:
            # Alexa correctly guessed object, now showing study info
            attributes_manager.persistent_attributes["last-state-guess"] = False
            attributes_manager.save_persistent_attributes()
            if attributes_manager.persistent_attributes["guess"][-1] == "doktor.json":
                # General study info is provided by separate handler
                # Shown when doktor.json was correct object
                return GeneralStudyInfoIntendHandler().handle(handler_input, arrive=True)
            # Other objects: normal subject info intent handler
            return StudyInfoIntendHandler().handle(handler_input)
        else:
            # Basicly ignore yes
            attributes_manager.save_persistent_attributes()
            speak_output = "Sehe ich ganz genau so."
            return (
                handler_input.response_builder
                    .speak(speak_output)
                    .ask(speak_output)
                    .response
            )


class NoIntentHandler(AbstractRequestHandler):
    """Handler for rejecting statements."""

    def can_handle(self, handler_input):
        return ask_utils.is_intent_name("AMAZON.NoIntent")(handler_input)

    def handle(self, handler_input):
        attributes_manager = handler_input.attributes_manager
        attributes_manager.persistent_attributes["state"] = "no"
        if "last-state-guess" in attributes_manager.persistent_attributes and attributes_manager.persistent_attributes["last-state-guess"] is True:
            # Alexa did not guess correctly
            selected_object = attributes_manager.persistent_attributes["guess"][1]
            complete_objects = attributes_manager.persistent_attributes["complete"]
            attributes_manager.persistent_attributes["last-state-guess"] = False
            complete_objects.remove(selected_object)
            attributes_manager.save_persistent_attributes()
            # Check if time out is applicable
            attributes_manager.persistent_attributes["wrong"] += 1
            if attributes_manager.persistent_attributes["wrong"] >= 3:
                attributes_manager.persistent_attributes.pop("guess")
                welcome = "Ich glaube, ich krieg es nicht raus. "
                return HomeScreenIntentHandler().handle(handler_input, welcome)
            speak_output = random.choice(get_features(UTTERANCES)["wrong_guess"])
            attributes_manager.save_persistent_attributes() 
            apl_doc = load_apl_document(HIDDENOBJECT_NOTOUCH_APL)
            data_doc = load_apl_document(STUDYINFOMAIN_DATA)
            data_doc["hiddenObjectsImage"]["highlightObjectsOn"] = create_presigned_url(data_doc["hiddenObjectsImage"]["highlightObjectsOn"])
            data_doc["hiddenObjectsImage"]["highlightObjectsOff"] = create_presigned_url(data_doc["hiddenObjectsImage"]["highlightObjectsOff"])
            logging.info(print("Data Doc No intent", data_doc))
            logging.info(print(attributes_manager.persistent_attributes["state"]))
            return (
                handler_input.response_builder
                    .speak(speak_output)
                    .ask(speak_output)
                    .add_directive(
                        RenderDocumentDirective(
                            document=apl_doc,
                            datasources=data_doc
                        )
                    )
                    .response
             )
        else:
            return CancelOrStopIntentHandler().handle(handler_input)


class AgainIntentHandler(AbstractRequestHandler):

    def can_handle(self, handler_input):
        return ask_utils.is_intent_name("AgainIntent")(handler_input)

    def handle(self, handler_input):
        speak_output = "Alles klar. Hier kannst du den Spielmodus wählen."
        return HomeScreenIntentHandler().handle(handler_input, welcome=speak_output)


class QueryIntentHandler(AbstractRequestHandler):
    """This handler deals with yes/no questions asked by the user."""

    def can_handle(self, handler_input):
        return ask_utils.is_intent_name("QueryIntent")(handler_input)

    def handle(self, handler_input):
        attributes_manager = handler_input.attributes_manager
        descr_obj = attributes_manager.persistent_attributes["described_object"]
        descr_obj = HiddenObject.from_json_dict(descr_obj)
        slots = handler_input.request_envelope.request.intent.slots
        possible_slots = ["shape", "location", "color", "other_description"]
        attributes_manager.save_persistent_attributes()
        speak_output = random.choice(get_features(UTTERANCES)["unsure"])
        for slot in possible_slots:
            feature_dict = descr_obj.feature_dict[slot]
            logging.info(print(feature_dict))
            if slots is not None and slots[slot].value is not None:
                # Use id to avoid to many similar descriptions in complete objects.
                try:
                    slot_id = slots[slot].resolutions.resolutions_per_authority[0].values[0].value.id
                # For inbuilt slots there seem to be no id.
                except (AttributeError, TypeError):
                    slot_id = slots[slot].value
                if slot_id in feature_dict:
                    speak_output = random.choice(get_features(UTTERANCES)["correct"])
                else:
                    speak_output = random.choice(get_features(UTTERANCES)["wrong"])
                    logging.info(print(slot, slot_id))
        return (
            handler_input.response_builder
                .speak(speak_output)
                .ask(speak_output)
                .response
        )


class DeadEndIntentHandler(AbstractRequestHandler):
    """No way, José"""
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return ask_utils.is_intent_name("DeadEndIntent")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        speak_output = "Diese Frage kann ich dir nicht beantworten. Wenn du nicht weiter weißt, sage einfach 'weiter' und ich gebe dir mehr Infos!"

        return (
            handler_input.response_builder
                .speak(speak_output)
                .ask(speak_output)
                .response
        )


class MoreIntentHandler(AbstractRequestHandler):
    """Give more information about the object."""

    def can_handle(self, handler_input):
        # Can handle if user utters wish for more info
        return ask_utils.is_intent_name("MoreIntent")(handler_input)

    def handle(self, handler_input):
        """Choose another attribute of the object and tell the user."""
        attributes_manager = handler_input.attributes_manager
        previous_state = attributes_manager.persistent_attributes.get("state")
        if previous_state  == "description":
            return DescriptionIntentHandler().handle(handler_input)
        attributes_manager.persistent_attributes["state"] = "more"
        attributes_manager.save_persistent_attributes()
        descr_obj_json = attributes_manager.persistent_attributes.get("described_object", False)
        if descr_obj_json is False:
            return HomeScreenIntentHandler().handle(handler_input, welcome="Irgendwas ist schief gegangen. ")
        descr_obj = HiddenObject.from_json_dict(descr_obj_json)
        speak_output = choose_description(descr_obj, handler_input)
        logging.info(print(attributes_manager.persistent_attributes["state"]))
        return (
            handler_input.response_builder
                .speak(speak_output)
                .ask(speak_output)
                .response
        )


class IsThatItIntentHandler(AbstractRequestHandler):
    """Handler for user making a guess."""
    
    def can_handle(self, handler_input):
        # Can handle if user utters a guess
        # ...and previous state is in choose_object, more
        attributes_manager = handler_input.attributes_manager
        return ask_utils.is_intent_name("IsThatItIntent")(handler_input) and attributes_manager.persistent_attributes["state"] in {"choose_object", "more"}

    def handle(self, handler_input, slot_id=""):
        """Show image for guessed object and ask user about it."""
        attributes_manager = handler_input.attributes_manager
        descr_obj_json = attributes_manager.persistent_attributes.get("described_object")
        descr_obj = HiddenObject.from_json_dict(descr_obj_json)
        name = get_name(descr_obj)

        if not slot_id:
            slots = handler_input.request_envelope.request.intent.slots
            logging.info(print("Slots for IsThatItIntent: ", slots))
            try:
                slot_id = slots["object"].resolutions.resolutions_per_authority[0].values[0].value.id
            except TypeError:
                slot_id = False
        logging.info(print("Guessed Object", slot_id))

        if slot_id == descr_obj.name:
            # If it is the doctor, go to GeneralStudyInfoIntendHandler
            if name == "der Doktor":
                return GeneralStudyInfoIntendHandler().handle(handler_input, arrive=True, show_obj=True)
            # Else: StudyInfoIntendHandler for specific subject
            return StudyInfoIntendHandler().handle(handler_input, show_obj=True)
        elif slot_id is False:
            speak_output = "Oh, das habe ich nicht richtig verstanden. Versuch es noch einmal. "
        elif attributes_manager.persistent_attributes["tries"] < 2:
            speak_output = "Das war leider falsch. Versuch es noch einmal oder frage nach mehr Informationen!"
            attributes_manager.persistent_attributes["tries"] += 1
        elif attributes_manager.persistent_attributes["tries"] >= 2:
            welcome = "Hmm, das scheint schwierig zu sein. Mein Objekt war {object}. ".format(object=name)
            return HomeScreenIntentHandler().handle(handler_input, welcome)
        attributes_manager.save_persistent_attributes() 
        return (
            handler_input.response_builder
                .speak(speak_output.format(object=name))
                .ask(speak_output)
                .response
        )


class HelpIntentHandler(AbstractRequestHandler):
    """Handler for Help Intent."""

    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return ask_utils.is_intent_name("AMAZON.HelpIntent")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        speak_output = "You can say hello to me! How can I help?"

        return (
            handler_input.response_builder
                .speak(speak_output)
                .ask(speak_output)
                .response
        )


class CancelOrStopIntentHandler(AbstractRequestHandler):
    """Single handler for Cancel and Stop Intent."""

    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return (ask_utils.is_intent_name("AMAZON.CancelIntent")(handler_input) or
                ask_utils.is_intent_name("AMAZON.StopIntent")(handler_input))

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        speak_output = "Okay, dann Tschüss!"

        return (
            handler_input.response_builder
                .speak(speak_output)
                .set_should_end_session(True)
                .response
        )


class SessionEndedRequestHandler(AbstractRequestHandler):
    """Handler for Session End."""

    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return ask_utils.is_request_type("SessionEndedRequest")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response

        # Any cleanup logic goes here.

        return handler_input.response_builder.response


class IntentReflectorHandler(AbstractRequestHandler):
    """The intent reflector is used for interaction model testing and debugging.
    It will simply repeat the intent the user said. You can create custom handlers
    for your intents by defining them above, then also adding them to the request
    handler chain below.
    """

    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return ask_utils.is_request_type("IntentRequest")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        intent_name = ask_utils.get_intent_name(handler_input)
        speak_output = "You just triggered " + intent_name + "."

        return (
            handler_input.response_builder
                .speak(speak_output)
                # .ask("add a reprompt if you want to keep the session open for the user to respond")
                .response
        )


class CatchAllExceptionHandler(AbstractExceptionHandler):
    """Generic error handling to capture any syntax or routing errors. If you receive an error
    stating the request handler chain is not found, you have not implemented a handler for
    the intent being invoked or included it in the skill builder below.
    """

    def can_handle(self, handler_input, exception):
        # type: (HandlerInput, Exception) -> bool
        return True

    def handle(self, handler_input, exception):
        # type: (HandlerInput, Exception) -> Response
        logger.error(exception, exc_info=True)

        speak_output = "Fehler: {}".format(exception)

        return (
            handler_input.response_builder
                .speak(speak_output)
                .ask(speak_output)
                .response
        )

# The SkillBuilder object acts as the entry point for your skill, routing all request and response
# payloads to the handlers above. Make sure any new handlers or interceptors you've
# defined are included below. The order matters - they're processed top to bottom.


sb = CustomSkillBuilder(persistence_adapter=s3_adapter)

sb.add_request_handler(LaunchRequestHandler())
sb.add_request_handler(HomeScreenIntentHandler())
sb.add_request_handler(ExplanationIntentHandler())
sb.add_request_handler(TouchIntentHandler())
sb.add_request_handler(HiddenObjectIntentHandler())
sb.add_request_handler(ChooseWordIntentHandler())
sb.add_request_handler(ChooseObjectIntentHandler())
sb.add_request_handler(StartOtherDirectionIntent())
sb.add_request_handler(QueryIntentHandler())
sb.add_request_handler(DeadEndIntentHandler())
sb.add_request_handler(MoreIntentHandler())
sb.add_request_handler(IsThatItIntentHandler())
sb.add_request_handler(DescriptionIntentHandler())
sb.add_request_handler(AgainIntentHandler())
sb.add_request_handler(YesIntentHandler())
sb.add_request_handler(NoIntentHandler())
sb.add_request_handler(DontKnowIntentHandler())
sb.add_request_handler(HelpIntentHandler())
sb.add_request_handler(CancelOrStopIntentHandler())
sb.add_request_handler(SessionEndedRequestHandler())
sb.add_request_handler(IntentReflectorHandler()) # make sure IntentReflectorHandler is last so it doesn't override your custom intent handlers

sb.add_exception_handler(CatchAllExceptionHandler())

lambda_handler = sb.lambda_handler()