# Сниппеты Remnawave

Нужны Remnawave Panel 3.2.3 или новее, совместимая Remnawave Node с первичной загрузкой геоданных (функция появилась в 3.1.1) и Xray с поддержкой `geodata`. Node загружает отсутствующие файлы перед запуском Xray. Дальше Xray скачивает и перечитывает их каждый понедельник в **02:30 по времени контейнера**. Скачивание по расписанию использует обычную маршрутизацию Xray. Это расписание работает отдельно от GitHub Actions. [Remnawave Panel](https://f.docs.rw/t/topic/518/2), [Remnawave Node](https://f.docs.rw/t/topic/520), [Xray geodata](https://xtls.github.io/en/config/geodata.html)

## Как подключить

1. В **Config Profiles → `{ }` Snippets** откройте существующий сниппет геоданных. Из [GEODATA.json](GEODATA.json) добавьте два объекта BADBOX в его `geodata.assets` и задайте `"cron": "30 2 * * 1"`. Сохраните текущие объекты `security.dat`, `security-ip.dat` и их URL. JSON-файл показывает полный пример сниппета с официальными адресами Chocolate4U и целевыми ссылками BADBOX. Перед применением убедитесь, что оба URL BADBOX скачиваются. [Chocolate4U](https://github.com/Chocolate4U/Iran-v2ray-rules#-how-to-download)
2. В корневом массиве `snippets` профиля должна быть строка с фактическим именем сниппета геоданных. Пример для имени `GEODATA`. Если `geodata` уже задан прямо в профиле, перенесите его в сниппет. Remnawave отдаёт приоритет полям самого профиля. [Слияние корневых сниппетов](https://github.com/remnawave/backend/commit/ae27a1ca3210abb0fa34e560f38dd673a3a86a51)

   ```json
   "snippets": ["GEODATA"]
   ```

3. Создайте или обновите сниппет `BADBOX-RULES` из одноимённого [JSON-файла](BADBOX-RULES.json). В каждом правиле укажите тег существующего outbound с `"protocol": "blackhole"`. В примере используется `BLOCK`. Правила с `ip` и `port` блокируют индикаторы, для которых в источниках указаны конкретные порты. Добавьте следующий объект в текущий `routing.rules` перед разрешающими правилами. [Сниппеты профиля](https://docs.rw/learn-en/config-profiles/#use-snippets), [Порядок правил Xray](https://xtls.github.io/en/config/routing.html#routingobject)

   ```json
   {"snippet": "BADBOX-RULES"}
   ```

4. Сохраните профиль. Для применения правок сниппета подтвердите синхронизацию при сохранении или перезапустите нужную ноду в **Nodes → Management**. Синхронизация сниппета перезапускает все ноды с использующими его профилями. [Синхронизация Remnawave](https://github.com/remnawave/backend/commit/ae27a1ca3210abb0fa34e560f38dd673a3a86a51), [Управление нодами](https://docs.rw/learn-en/nodes/)

5. Убедитесь, что нода в сети и Xray стартовал с новым профилем. При первичной загрузке в журнале Node проверьте `Downloaded "badbox.dat"` и `Downloaded "badbox-ip.dat"`. После планового обновления в журнале Xray с уровнем `info` проверьте попытки `downloading geodata asset` для обоих файлов и отсутствие ошибки `scheduled geodata reload failed`. [Загрузчик Node](https://github.com/remnawave/node/blob/3.4.6/src/modules/xray-core/geodata.service.ts), [Журналы Xray](https://docs.rw/guides/useful-commands/#access-xray-core-logs), [Планировщик Xray](https://github.com/XTLS/Xray-core/blob/v26.11.9/app/geodata/geodata.go)

Доменное правило проверяет имя назначения, когда оно доступно Xray. Правило IP проверяет известный IP назначения. Определение IP из имени зависит от текущей `routing.domainStrategy` и порядка правил. [Маршрутизация Xray](https://xtls.github.io/en/config/routing.html#routingobject)

Для опциональной блокировки сайтов рекламной схемы H5 добавьте актив `badbox-h5.dat` в `geodata.assets` и отдельное правило `domain` со значением `ext:badbox-h5.dat:badbox`. Используйте тот же блокирующий outbound. [Скачать badbox-h5.dat](https://raw.githubusercontent.com/zeffbtw/badbox-geodata/main/dist/badbox-h5.dat)

## Откат

В истории GitHub выберите один рабочий коммит. В URL подключённых DAT BADBOX замените `main` на полный SHA этого коммита, затем возьмите `BADBOX-RULES` из той же версии и примените профиль к нодам. Уже существующие DAT будут заменены при ближайшем запуске по расписанию. Чтобы сразу отключить блокировку BADBOX, уберите `{"snippet": "BADBOX-RULES"}` из `routing.rules` и примените профиль. [Загрузка при старте Node](https://f.docs.rw/t/topic/520), [Обновление по расписанию Xray](https://xtls.github.io/en/config/geodata.html)
