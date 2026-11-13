from aiogram.fsm.state import State, StatesGroup


class Registration(StatesGroup):
    name, age, city, gender, target_gender, text, media = [State() for _ in range(7)]

class EditProfile(StatesGroup):
    choosing_field = State()

class SearchState(StatesGroup):
    browsing = State()
    writing_message = State()
    choosing_report = State()
