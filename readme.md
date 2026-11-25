# badbox-geodata

Два небольших списка для Xray и Remnawave. Они покрывают проверенные индикаторы инфраструктуры BADBOX, BADBOX 2.0 и BADBOX 3.0 из перечисленных источников и дополняют `security.dat` и `security-ip.dat` от Chocolate4U. Покрытие ограничено опубликованными и проверенными индикаторами.

| Файл | Публичный HTTPS | Правило Xray |
| --- | --- | --- |
| GeoSite | [badbox.dat](https://raw.githubusercontent.com/zeffbtw/badbox-geodata/main/dist/badbox.dat) | `ext:badbox.dat:badbox` |
| GeoIP | [badbox-ip.dat](https://raw.githubusercontent.com/zeffbtw/badbox-geodata/main/dist/badbox-ip.dat) | `ext:badbox-ip.dat:badbox` |

[SHA-256](dist/SHA256SUMS) и [отчёт](dist/report.json) содержат дату сборки в UTC, размеры, число уникальных правил, источники и результаты сверки. Оба DAT и отчёт публикуются одним коммитом. Для проверки или отката фиксированной версии скачайте оба файла, отчёт и контрольные суммы по одному SHA коммита. [История сборок](https://github.com/zeffbtw/badbox-geodata/commits/main/dist)

## Подключение

Готовые [GEODATA](snippets/GEODATA.json) и [BADBOX-RULES](snippets/BADBOX-RULES.json) подключаются через [сниппеты Remnawave](snippets/README.md). Нода загружает отсутствующие файлы перед стартом Xray. Затем Xray обновляет их по понедельникам в 02:30 по времени контейнера.

## Источники

| Вариант | Что сверяем | Обновление |
| --- | --- | --- |
| BADBOX | C2 из приложения отчёта, включая C2 рекламного модуля PEACHPIT, который загружал BADBOX. [Обзор HUMAN](https://www.humansecurity.com/company/satori-threat-intelligence/badbox/), [PDF с IOC](https://www.humansecurity.com/hubfs/HUMAN_Report_BADBOX-and-PEACHPIT.pdf) | Приложение PDF ежедневно |
| BADBOX | Дополнительные хосты из исследования HUMAN и адреса серверов, наблюдавшихся при исследовании доставки компонентов. [Разбор HUMAN](https://www.humansecurity.com/learn/blog/trojans-all-the-way-down-badbox-and-peachpit/), [разбор Bitsight](https://www.bitsight.com/blog/badbox-botnet-back) | По результатам ручной сверки |
| BADBOX 2.0 | Таблица C2, хосты доставки и прокси с опубликованных схем и домены сайтов монетизации Hidden WebViews/H5. [Публикация HUMAN](https://www.humansecurity.com/learn/blog/satori-threat-intelligence-disruption-badbox-2-0/), [приложение H5 CSV](https://www.humansecurity.com/wp-content/uploads/2025/03/BADBOX-2-H5-Domain-List.csv) | CSV ежедневно, статья и схемы вручную |
| BADBOX 2.0 | `jm.ttyunos.com` наблюдался у Android-приставок как конкретный хост доставки. Связь с BADBOX 2.0 установлена по включению `ttyunos.com` в таблицу C2 HUMAN. [Zero-Entry](https://zero-entry.co.za/posts/when-you-tell-the-device-no/#the-android-tv-box-720), [Caesar Creek Software](https://cc-sw.com/set-top-box-re-6-part-series-6-of-6/), [таблица HUMAN](https://www.humansecurity.com/learn/blog/satori-threat-intelligence-disruption-badbox-2-0/#list-of-c2-domains) | По результатам ручной сверки |
| BADBOX 3.0 | Все 33 индикатора из трёх таблиц IOC, включая C2, доставку, рекламные хосты и PXYEDGE. [Публикация HUMAN](https://www.humansecurity.com/learn/blog/satori-threat-intelligence-disruption-badbox-3-0-hides-the-largest-ad-fraud-operation-ever-disclosed-inside-infected-tv-boxes/) | Сверка по сохранённому HTML. При повторной прямой загрузке сервер возвращал HTTP 403 |

Домен с правилом `full` сопоставляется точно. Правило `domain` также покрывает поддомены и требует обоснования в исходных данных. IP-адреса в текущей сборке имеют префикс `/32`. Для подтверждённого C2 `47.113.90.237/32` правило действует на все порты этого IP, на котором также встречались страницы производителя. В [исключениях](data/) записаны причины для общих платформ, адресов клиентов ботнета, DNS-соседей, неделегированных имён и других записей. Для H5 делегирование проверяется по сохранённому [списку зон IANA](https://data.iana.org/TLD/tlds-alpha-by-domain.txt). GeoSite оперирует именами хостов, поэтому путь на общем хосте GitHub исключён, а отдельный бакет Alibaba Cloud добавлен точным именем.

## Автообновление и проверка

[GitHub Actions](.github/workflows/geodata.yml) запускается ежедневно в 04:17 UTC, вручную через **Run workflow** и при изменении входных данных, кода или настроек сборки в `main`. Парсеры скачивают C2-приложение PDF и H5 CSV, проверяют формат и сверяют список с предыдущим снимком. Новые подтверждённые строки добавляются в `data/badbox-refresh.json` с датой и источником. При неудачной загрузке, смене структуры или необъяснимой пропаже строк задача завершается ошибкой и GitHub продолжает отдавать предыдущий коммит. При прежних данных нового коммита нет. Workflow использует только встроенное разрешение `contents: write`.

Проект использует Python ≥3.11, `curl`, `pdftotext` из Poppler и Xray v26.11.9. Проверка перечитывает DAT, сверяет каждую запись с правилами, тестирует границы доменов и IP и запускает `xray run -test` с обоими `ext:`. Проверки покрытия работают локально по DAT. Замеры RAM не проводились.

```sh
python3 scripts/refresh.py
python3 scripts/build.py --xray /path/to/xray
(cd dist && shasum -a 256 -c SHA256SUMS)
```

Для сверки BADBOX 3.0 сохраните HTML первоисточника как `human-badbox3.html` и передайте его каталог через `python3 scripts/refresh.py --snapshot-dir /path/to/snapshots`. Для новых публикаций сначала проверьте относимость индикаторов и добавьте записи с источником, вариантом, ролью и датой в `data/badbox-*.json`. Для перевода источника на автоматическое обновление добавьте конфигурацию в `data/feeds.json`, строгий парсер и его регистрацию в `scripts/refresh.py`. При ручном снятии записи внесите исходный индикатор и его источник в `data/exclusions-*.json` с причиной. Если подтверждено сокращение приложения, обновите соответствующий минимальный размер таблицы в конфигурации или парсере.
