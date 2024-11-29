

from aiogram import Bot, Dispatcher, types
from aiogram import executor
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.contrib.fsm_storage.memory import MemoryStorage
import aiohttp
from crud_functions import initiate_db, get_all_products, add_user, is_included

# API_TOKEN = 'YOUR_API_TOKEN'  # Заменить 'YOUR_API_TOKEN' на токен бота

bot = Bot(token='7899777709:AAF8GMkfdfh6PKJAVzhZulwUFxzPtwQ3VaE')
dp = Dispatcher(bot, storage=MemoryStorage())


class UserState(StatesGroup):
    age = State()
    growth = State()
    weight = State()
    sex = State()


class RegistrationState(StatesGroup):
    username = State()
    email = State()
    age = State()


# Инициализация базы данных
initiate_db()

keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
button_calculate = KeyboardButton('Рассчитать')
button_info = KeyboardButton('Информация')
button_buy = KeyboardButton('Купить')
button_register = KeyboardButton('Регистрация')  # Кнопка регистрации
keyboard.add(button_calculate, button_info, button_buy, button_register)

inline_keyboard = InlineKeyboardMarkup()
button_calories = InlineKeyboardButton(text='Рассчитать норму калорий', callback_data='calories')
button_formulas = InlineKeyboardButton(text='Формулы расчёта', callback_data='formulas')
inline_keyboard.add(button_calories, button_formulas)


@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    response_text = 'Привет! Я бот, помогающий твоему здоровью.'
    await message.reply(response_text, reply_markup=keyboard)


@dp.message_handler(lambda message: message.text == 'Регистрация')
async def sing_up(message: types.Message):
    await RegistrationState.username.set()  # Устанавливаем состояние для username
    await message.reply("Введите имя пользователя (только латинский алфавит):")


@dp.message_handler(state=RegistrationState.username)
async def set_username(message: types.Message, state: FSMContext):
    username = message.text
    if is_included(username):
        await message.reply("Пользователь существует, введите другое имя.")
    else:
        await state.update_data(username=username)
        await RegistrationState.next()  # Переход к следующему состоянию
        await message.reply("Введите свой email:")


@dp.message_handler(state=RegistrationState.email)
async def set_email(message: types.Message, state: FSMContext):
    email = message.text
    await state.update_data(email=email)
    await RegistrationState.next()  # Переход к следующему состоянию
    await message.reply("Введите свой возраст:")


@dp.message_handler(state=RegistrationState.age)
async def set_age(message: types.Message, state: FSMContext):
    age = message.text
    user_data = await state.get_data()
    username = user_data.get("username")
    email = user_data.get("email")

    add_user(username, email, age)  # Добавляем пользователя в БД
    await message.reply("Вы успешно зарегистрированы!")
    await state.finish()  # Завершаем состояние


# Создание инлайн-клавиатуры для покупки
def create_product_inline_keyboard():
    product_inline_keyboard = InlineKeyboardMarkup()
    products_info = get_all_products()
    for index, product in enumerate(products_info):
        button_product = InlineKeyboardButton(text=product[4], callback_data=f'product_buying_{index}')
        product_inline_keyboard.add(button_product)
    return product_inline_keyboard


@dp.message_handler(lambda message: message.text == 'Рассчитать')
async def main_menu(message: types.Message):
    await message.reply('Выберите опцию:', reply_markup=inline_keyboard)


@dp.message_handler(lambda message: message.text == 'Купить')
async def get_buying_list(message: types.Message):
    products_inf = get_all_products()  # Получаем все продукты из базы данных
    for product in products_inf:
        title, description, price, url, short_name = product
        await message.reply(f'Название: {title} | Описание: {description} | Цена: {price}')

        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status == 200:
                    photo = await resp.read()
                    await bot.send_photo(message.chat.id, photo=photo)
                else:
                    await message.reply("Изображение недоступно.")

    product_inline_keyboard = create_product_inline_keyboard()  # Создаем клавиатуру один раз
    await message.reply('Выберите продукт для покупки:', reply_markup=product_inline_keyboard)


@dp.callback_query_handler(lambda call: call.data.startswith('product_buying'))
async def send_confirm_message(call: types.CallbackQuery):
    product_index = int(call.data.split('_')[2])  # Получаем индекс продукта из callback_data
    products_info = get_all_products()
    product_title = products_info[product_index][0]  # Получаем название продукта
    await bot.answer_callback_query(call.id)
    await bot.send_message(call.from_user.id, f"Вы успешно приобрели продукт: {product_title}!")


@dp.callback_query_handler(lambda call: call.data == 'formulas')
async def get_formulas(call: types.CallbackQuery):
    formula_info = ("Формула Миффлина - Сан Жеора:\n"
                    "Для женщин: 10 * вес + 6.25 * рост - 5 * возраст - 161\n"
                    "Для мужчин: 10 * вес + 6.25 * рост - 5 * возраст + 5")
    await bot.answer_callback_query(call.id)
    await bot.send_message(call.from_user.id, formula_info)


@dp.callback_query_handler(lambda call: call.data == 'calories')
async def set_sex(call: types.CallbackQuery):
    await bot.answer_callback_query(call.id)
    await bot.send_message(call.from_user.id, 'Введите свой пол (м/ж):')
    await UserState.sex.set()  # Устанавливаем состояние для пола


@dp.message_handler(state=UserState.age)
async def set_growth(message: types.Message, state: FSMContext):
    try:
        age = int(message.text)
        if age < 0 or age > 120:  # пример проверки валидности возраста
            raise ValueError
        await state.update_data(age=age)
        await message.reply('Введите свой рост (в см):')
        await UserState.growth.set()
    except ValueError:
        await message.reply('Пожалуйста, введите корректный возраст!')


@dp.message_handler(state=UserState.sex)
async def set_age(message: types.Message, state: FSMContext):
    if message.text.lower() not in ['м', 'ж']:
        await message.reply('Пожалуйста, введите "м" для мужчин или "ж" для женщин.')
        return
    await state.update_data(sex=message.text.lower())
    await message.reply('Введите свой возраст:')
    await UserState.age.set()


@dp.message_handler(state=UserState.growth)
async def set_weight(message: types.Message, state: FSMContext):
    try:
        growth = int(message.text)
        if growth <= 0:  # проверка на положительность роста
            raise ValueError
        await state.update_data(growth=growth)
        await message.reply('Введите свой вес (в кг):')
        await UserState.weight.set()
    except ValueError:
        await message.reply('Пожалуйста, введите корректный рост в сантиметрах!')


@dp.message_handler(state=UserState.weight)
async def send_calories(message: types.Message, state: FSMContext):
    try:
        weight = int(message.text)
        if weight <= 0:  # проверка на положительность веса
            raise ValueError
        await state.update_data(weight=weight)
        data = await state.get_data()
        age = data.get('age')
        growth = data.get('growth')
        weight = data.get('weight')
        sex = data.get('sex')

        if sex == 'ж':
            calories = 10 * weight + 6.25 * growth - 5 * age - 161
        else:
            calories = 10 * weight + 6.25 * growth - 5 * age + 5
        await message.reply(f'Ваша норма калорий: {calories:.2f} ккал')
        await state.finish()  # Завершаем состояние
    except ValueError:
        await message.reply('Пожалуйста, введите корректный вес в килограммах!')


@dp.message_handler(lambda message: message.text == 'Информация')
async def info(message: types.Message):
    await message.reply('Информация о боте: Я предназначен для расчета калорий и улучшения Вашего здоровья.')


@dp.message_handler(lambda message: True)
async def all_messages(message: types.Message):
    await message.reply('Введите команду /start или нажмите на кнопку, чтобы начать общение.')


if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)