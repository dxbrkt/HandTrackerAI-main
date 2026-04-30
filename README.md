# HandTracker AI

Жестовый интерфейс управления для macOS с отдельным окном, SDK-слоем и демонстрационным приложением.

## Что уже реализовано

- Детекция руки и ключевых точек через MediaPipe Hands
- Распознавание статических жестов: `open_palm`, `pinch`, `fist`, `thumbs_up`
- Распознавание динамических жестов: `swipe_left`, `swipe_right`, `two_fingers_up`, `two_fingers_down`
- Управление macOS через `pyautogui`
- Демонстрационное окно на `tkinter` с живым видеопотоком и телеметрией задержки
- SDK-структура для дальнейшего обучения/расширения жестов

## Запуск

1. Установите Python 3.10+
2. Создайте виртуальное окружение
3. Установите зависимости
4. Запустите демо

```bash
python3 -m venv venv
source venv/bin/activate
pip3 install -r requirements.txt
PYTHONPATH=src python3 -m handtracker_ai.main

source .venv311/bin/activate
PYTHONPATH=src python -m handtracker_ai.main

--------------------------------------
python3.11 -m venv .venv311
source .venv311/bin/activate
pip install -r requirements.txt
PYTHONPATH=src python -m handtracker_ai.main

```

## Сборка в macOS `.app`

1. Активируйте окружение проекта
2. Установите `PyInstaller`
3. Запустите скрипт сборки

```bash
source .venv311/bin/activate
python -m pip install pyinstaller
./scripts/build_macos_app.sh
```

После сборки приложение появится в `dist/HandTrackerAI.app`.

При первом запуске macOS может:

- спросить доступ к камере
- попросить разрешение в `Privacy & Security -> Accessibility`, чтобы жесты могли управлять системой

Если macOS заблокирует запуск неподписанного приложения, откройте его через Finder: `Right click -> Open`.


## Жесты и действия

- `open_palm` — открытая ладонь. Перемещает курсор мыши вслед за движением руки.
- `pinch` —    епотка, когда большой и указательный палец сведены вместе. Выполняет левый клик мыши.
- `fist` — сжатый кулак. Нажимает клавишу `Space`, что обычно работает как `play/pause` в медиаплеерах.
- `swipe_left` — быстрое движение рукой влево. Переключает рабочий стол macOS влево через `Ctrl + Left`.
- `swipe_right` — быстрое движение рукой вправо. Переключает рабочий стол macOS вправо через `Ctrl + Right`.
- `thumbs_up` — поднятый большой палец. Увеличивает громкость системы.
- `thumbs_down` — опущенный большой палец. Уменьшает громкость системы.
- `two_fingers_up` — указательный и средний палец вверх, затем движение рукой вверх. Прокручивает содержимое вверх.
- `two_fingers_down` — указательный и средний палец вверх, затем движение рукой вниз. Прокручивает содержимое вниз.

## Важно для macOS

Чтобы приложение управляло системой, выдайте терминалу или Python-интерпретатору доступ:
∂     
`System Settings -> Privacy & Security -> Accessibility`

И для камеры:

`System Settings -> Privacy & Security -> Camera`

## Приемка и развитие

Текущая версия дает стартовый SDK + demo app и оптимизирована под низкую задержку за счет:

- lightweight-пайплайна MediaPipe
- одного обрабатываемого жестового канала
- сглаживания курсора без тяжелой постобработки

Для выхода на устойчивую точность `>= 80%` в целевой среде рекомендуется:

- собрать свой датасет жестов под вашу камеру и освещение
- добавить калибровку порогов под пользователя
- подключить отдельную модель для динамических жестов (`LSTM`/`C3D`)
- добавить профили действий для разных приложений

## Источники

1. MediaPipe Hands: <https://developers.google.com/mediapipe>
2. YOLO: <https://pjreddie.com/darknet/yolo>
3. C3D: <https://arxiv.org/abs/1412.0767>
4. LSTM: <https://www.bioinf.jku.at/publications/older/2604.pdf>
5. TensorRT: <https://developer.nvidia.com/tensorrt>
6. Jetson SDK: <https://developer.nvidia.com/embedded/jetson>
7. OpenCV: <https://opencv.org>
  
