from config import USE_PROVIDER

def get_provider():
    if USE_PROVIDER == 'green':
        from .green_api import GreenAPI
        return GreenAPI()
    elif USE_PROVIDER == 'twilio':
        from .twilio_api import TwilioAPI
        return TwilioAPI()
    else:
        raise ValueError("Unknown provider")
