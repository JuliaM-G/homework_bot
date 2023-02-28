import logging
import os
import requests
import sys
import telegram
import time

from http import HTTPStatus

from dotenv import load_dotenv

import exceptions
from settings import ENDPOINT, HOMEWORK_VERDICTS, RETRY_PERIOD

load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

logger = logging.getLogger(__name__)


def check_tokens():
    """Проверка дотсупности переменных."""
    return all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID])


def send_message(bot, message):
    """Отправка сообщений."""
    logger.info('Сообщение отправлено')
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.debug(
            f'Сообщение в Telegram отправлено: {message}')
    except telegram.error.TelegramError as error:
        logger.error(
            f'Сообщение в Telegram не отправлено: {error}')


def get_api_answer(timestamp):
    """Получение ответа о статусе проверки работы."""
    params_request = {
        'url': ENDPOINT,
        'headers': HEADERS,
        'params': {'from_date': timestamp},
    }
    try:
        logging.info(
            f'Начало запроса: url = {ENDPOINT},'
            f'headers = {HEADERS},'
            f'params = {params_request}',
        )
        homework_statuses = requests.get(**params_request)
        if homework_statuses.status_code != HTTPStatus.OK:
            raise exceptions.InvalidResponseCode(
                'Не удалось получить ответ API, '
                f'Ошибка: {homework_statuses.status_code}'
                f'Причина: {homework_statuses.reason}'
                f'Текст: {homework_statuses.text}'
            )
        return homework_statuses.json()
    except Exception:
        raise exceptions.ConnectinError(
            f'Неверный код ответа: url = {ENDPOINT},'
            f'headers = {HEADERS},'
            f'params = {params_request}',
        )


def check_response(response):
    """Проверка валидности ответа."""
    logging.debug('Начало проверки')
    if not isinstance(response, dict):
        raise TypeError('Ошибка в типе ответа API')
    if 'homeworks' not in response or 'current_date' not in response:
        raise exceptions.EmptyResponseFromAPI('Пустой ответ API')
    homeworks = response.get('homeworks')
    if not isinstance(homeworks, list):
        raise TypeError('Homeworks не является списком')
    return homeworks


def parse_status(homework):
    """Извлечение информации о статусе работы."""
    homework_name = homework.get('homework_name')
    if 'homework_name' not in homework:
        raise KeyError('Такой домашней работы нет')
    homework_status = homework.get('status')
    if 'status' not in homework:
        raise exceptions.UnknownStatus('Неизвестный статус работы')
    if homework_status not in HOMEWORK_VERDICTS:
        raise KeyError('Неизвестный статус работы')
    verdict = HOMEWORK_VERDICTS[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logging.critical('Отсутсвует необходимое количество'
                         ' переменных')
        sys.exit('Отсутсвуют переменные')

    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    last_message = 'messages'

    while True:
        try:
            response = get_api_answer(timestamp)
            timestamp = response.get(
                'current_data', timestamp
            )
            new_homeworks = check_response(response)
            if new_homeworks:
                homework = new_homeworks[0]
                status = parse_status(homework)
            else:
                status = 'Новые статусы отсутсвуют.'
            if status != last_message:
                last_message = status
                send_message(bot, message=status)
            else:
                logging.debug('Статус не изменился')
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            last_message = status
            logging.error(message)
            if status != last_message:
                send_message(bot, message=status)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format=(
            '%(asctime)s, %(levelname)s, Путь - %(pathname)s, '
            'Файл - %(filename)s, Функция - %(funcname)s, '
            'Номер строки - %(lineno)d, %(message)s'
        ),
        handlers=[logging.FileHandler('log.txt', encoding='UTF-8'),
                  logging.StreamHandler(sys.stdout)]
    )
    main()
