# Загрузка проекта на GitHub

Для публикации нужны исходники, а не установленные зависимости. Если подготовлена отдельная папка `github-upload`, загружайте **её содержимое**, сохраняя вложенные каталоги. README.md, main.py, setup.bat и package.json должны оказаться в корне репозитория.

1. Создайте пустой репозиторий, например `HTML-Presentation-Converter`.
2. Откройте страницу репозитория и выберите загрузку существующих файлов. Для уже созданного репозитория: **Add file → Upload files**.
3. Перетащите файлы и папки проекта в область загрузки. Включите `.gitignore` и `.gitattributes`.
4. Проверьте, что видны каталоги converter, renderer, examples, tests, tools и docs.
5. Сохраните загрузку коммитом, например с сообщением `Добавить HTML Presentation Converter`.

В репозитории не нужны `.git`, `.venv`, `.runtime`, node_modules, кэши, tmp, test-results и пользовательские результаты PDF/PPTX. Отдельная загрузка Chromium тоже не нужна. После скачивания исходников зависимости устанавливаются через setup.bat.

Инструкция сервиса: [добавление файлов в репозиторий — GitHub Docs](https://docs.github.com/en/repositories/working-with-files/managing-files/adding-a-file-to-a-repository).
