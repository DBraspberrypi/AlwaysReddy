import time
from config_loader import config
import prompt
from actions.base_action import BaseAction
from utils import to_clipboard
import prompt

class AlwaysReddyVoiceAssistant(BaseAction):
    """Action for handling voice assistant functionality."""
    def setup(self):
        self.last_message_was_cut_off = False
        
        if config.RECORD_HOTKEY:
            # HOTKEY CONFIGURATION
            self.AR.add_action_hotkey(config.RECORD_HOTKEY, 
                                pressed=self.handle_default_assistant_response,
                                held_release=self.handle_default_assistant_response,
                                double_tap=self.AR.save_clipboard_text)
            
            print(f"'{config.RECORD_HOTKEY}': Start/stop talking to voice assistant (press to toggle on and off or hold-release)")
            if "+" in config.RECORD_HOTKEY:
                hotkey_start, hotkey_end = config.RECORD_HOTKEY.rsplit("+", 1)
                print(f"\tHold down '{hotkey_start}' and double tap '{hotkey_end}' to send clipboard content to AlwaysReddy")
            else:
                print(f"\tDouble tap '{config.RECORD_HOTKEY}' to send clipboard content to AlwaysReddy")

        if config.NEW_CHAT_HOTKEY:
            self.AR.add_action_hotkey(config.NEW_CHAT_HOTKEY, pressed=self.new_chat)
            print(f"'{config.NEW_CHAT_HOTKEY}': New chat for voice assistant")

        self.messages = prompt.build_initial_messages(config.ACTIVE_PROMPT)

    def handle_default_assistant_response(self):
        """Handle the response from the transcription and generate a completion."""
        try:
            recording_filename = self.AR.toggle_recording(self.handle_default_assistant_response)
            if not recording_filename:
                return
            message = self.AR.transcription_manager.transcribe_audio(recording_filename)

            if not self.AR.stop_action and message:
                print("\nTranscript:\n", message)
                
                if len(self.messages) > 0 and self.messages[0]["role"] == "system":
                    self.messages[0]["content"] = prompt.get_system_prompt_message(config.ACTIVE_PROMPT)

                if self.last_message_was_cut_off:
                    message = "--> USER CUT THE ASSISTANTS LAST MESSAGE SHORT <--\n" + message

                if self.AR.clipboard_text and self.AR.clipboard_text != self.AR.last_clipboard_text:
                    message += f"\n\nTHE USER HAS GANTED YOU ACCESS TO THEIR CLIPABORD, THIS IS ITS CONTENT (ignore if user doesn't mention it):\n```{self.AR.clipboard_text}```"
                    self.AR.last_clipboard_text = self.AR.clipboard_text
                    self.AR.clipboard_text = None
                
                if config.TIMESTAMP_MESSAGES:
                    message += f"\n\nMESSAGE TIMESTAMP:{time.strftime('%I:%M %p')} {time.strftime('%Y-%m-%d (%A)')} "

                self.messages.append({"role": "user", "content": message})

                if self.AR.stop_action:
                    return

                stream = self.AR.completion_client.get_completion_stream(self.messages, model=config.COMPLETION_MODEL)
                response = self.AR.completion_client.process_text_stream(stream,
                                                                         marker_tuples=[(config.CLIPBOARD_TEXT_START_SEQ, config.CLIPBOARD_TEXT_END_SEQ, to_clipboard)],
                                                                          sentence_callback=self.AR.tts.run_tts)#We pass in pairs of start and end sequences to the marker_tuples argument to indicate that the text between these sequences should be copied to the clipboard, then we pass the to_clipboard function as the callback to handle this action.
                    
                while self.AR.tts.running_tts:
                    time.sleep(0.001)

                if not response:
                    if self.AR.verbose:
                        print("No response generated.")
                    self.messages = self.messages[:-1]
                    return

                self.last_message_was_cut_off = False

                if self.AR.stop_action:
                    index = response.rfind(self.AR.tts.last_sentence_spoken)
                    if index != -1:
                        response = response[:index + len(self.AR.tts.last_sentence_spoken)]
                        self.last_message_was_cut_off = True

                self.messages.append({"role": "assistant", "content": response})
                print("\nResponse:\n", response)

        except Exception as e:
            if self.AR.verbose:
                import traceback
                traceback.print_exc()
            else:
                print(f"An error occurred while handling the response: {e}")


    def new_chat(self):
        """Clear the message history and start a new chat session."""
        self.messages = prompt.build_initial_messages(config.ACTIVE_PROMPT)
        self.last_message_was_cut_off = False
        self.AR.last_clipboard_text = None
        print("New chat session started.")