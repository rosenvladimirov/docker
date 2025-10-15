==============
Supervisor.py
==============

Python скрипт за управление и инсталиране на Odoo модули и добавки
================================================================

Преглед
-------

``supervisor.py`` е автоматизиран инструмент за настройване на Odoo инстанции с различни типове добавки.
Проектиран е за работа в контейнерни среди и поддържа управление на OCA модули, Enterprise добавки и
персонализирани разширения.

Характеристики
--------------

* 🔧 **Автоматизирано настройване** - Пълна конфигурация на Odoo среда
* 📦 **Управление на пакети** - Инсталиране и деинсталиране на Python зависимости
* 🔗 **Символни връзки** - Автоматично създаване на symlinks за модули
* 🌐 **OCA поддръжка** - Интеграция с Open Community Association репозитории
* 🏢 **Enterprise модули** - Поддръжка за официални Odoo Enterprise добавки
* 🐳 **Контейнер готовност** - Оптимизиран за Docker/Kubernetes среди
* 🔐 **Управление на права** - Автоматично настройване на файлови разрешения

Инсталиране
-----------

Скриптът не изисква специална инсталация. Просто изтеглете файла и го направете изпълним:

.. code-block:: bash

   chmod +x supervisor.py

Изисквания
----------

* Python 3.11+
* Git
* Права за писане в системните директории
* Интернет връзка за изтегляне на модули

Използване
----------

Основен синтаксис
~~~~~~~~~~~~~~~~

.. code-block:: bash

   python3 supervisor.py <конфигурационен_файл> [опции]

Примери
~~~~~~~

**Основна употреба:**

.. code-block:: bash

   python3 supervisor.py /path/to/addons.conf

**С OCA добавки:**

.. code-block:: bash

   python3 supervisor.py /path/to/addons.conf --addons-oca

**С Enterprise модули:**

.. code-block:: bash

   python3 supervisor.py /path/to/addons.conf --addons-ее

**Init container режим:**

.. code-block:: bash

   python3 supervisor.py /path/to/addons.conf --init-container

Командни опции
--------------

.. list-table::
   :header-rows: 1

   * - Опция
     - Описание
   * - ``-a, --odoo-addons-oca``
     - Инсталира OCA добавки
   * - ``-r, --odoo-addons``
     - Инсталира Odoo добавки
   * - ``-s, --source-dir``
     - Директория източник за добавките
   * - ``-t, --target-dir``
     - Целева директория за добавките
   * - ``--addons-oca``
     - Инсталира всички OCA добавки
   * - ``--force-update``
     - Принудително обновява конфигурацията
   * - ``--addons-ее``
     - Инсталира Enterprise добавки
   * - ``--init-container``
     - Активира строг режим за init контейнер
   * - ``-u, --uid``
     - UID на Odoo потребителя
   * - ``-g, --gid``
     - GID на Odoo потребителя

Конфигуриране
-------------

Конфигурационният файл използва INI формат:

.. code-block:: ini

   [global]
   force_update = true
   use_requirements = true

   [symlinks]
   source_dir = /opt/odoo/odoo-18.0
   target_dir = /var/lib/odoo/.local/share/Odoo/addons/18.0
   priority = base,web,mail

   [github]
   username = your_github_user
   email = your_email@example.com
   password = your_github_token

   [odoo]
   username = your_odoo_user
   password = your_odoo_password

   [apps.odoo.com]
   username = your_apps_user
   password = your_apps_password

   [owner]
   uid = 100
   gid = 100

   [addons]
   use_oca = true
   odoo_addons_oca = account-analytic,server-tools
   use_ee = false

   [uninstall]
   python_package = deprecated-package1,old-package2

Променливи на средата
---------------------

.. list-table::
   :header-rows: 1

   * - Променлива
     - Описание
     - По подразбиране
   * - ``ODOO_BRANCH``
     - Версия на Odoo клона
     - ``18.0``
   * - ``ODOO_INIT_CONTAINER``
     - Активира init режим
     - ``false``

Директории по подразбиране
--------------------------

* **Odoo директория**: ``/var/lib/odoo``
* **Opt директория**: ``/opt/odoo``
* **Python цел**: ``/opt/python3``
* **Допълнителни добавки**: ``/mnt/extra-addons``

Режими на работа
----------------

Обикновен режим
~~~~~~~~~~~~~~~

Стандартно изпълнение със самостоятелно обработване на грешки. Скриптът ще продължи
да работи дори при възникване на грешки в отделни операции.

Init Container режим
~~~~~~~~~~~~~~~~~~~~

Активира се с ``--init-container`` или променливата ``ODOO_INIT_CONTAINER``.
В този режим:

* Принудително се активират requirements
* Принудително се активира force_update
* Скриптът прекратява изпълнението при първа грешка (fail-fast)

Docker интеграция
-----------------

Пример Dockerfile:

.. code-block:: docker

   FROM python:3.11-slim

   COPY supervisor.py /usr/local/bin/
   COPY addons.conf /etc/odoo/

   RUN chmod +x /usr/local/bin/supervisor.py

   # Init контейнер
   CMD ["/usr/local/bin/supervisor.py", "/etc/odoo/addons.conf", "--init-container"]

Kubernetes пример:

.. code-block:: yaml

   apiVersion: v1
   kind: Pod
   spec:
     initContainers:
     - name: odoo-setup
       image: your-supervisor-image:latest
       command: ["/usr/local/bin/supervisor.py"]
       args: ["/etc/odoo/addons.conf", "--init-container"]
       env:
       - name: ODOO_BRANCH
         value: "18.0"
       - name: ODOO_INIT_CONTAINER
         value: "true"

Отстраняване на проблеми
------------------------

Общи проблеми
~~~~~~~~~~~~~

**Грешка при права на достъп:**

.. code-block:: bash

   sudo chown -R odoo:odoo /var/lib/odoo
   sudo chmod -R 755 /var/lib/odoo

**Git грешки:**

.. code-block:: bash

   # Проверете интернет връзката
   git config --global http.sslverify false  # Само за тестове

**Python пакети:**

.. code-block:: bash

   pip install --upgrade pip
   pip install --no-cache-dir -r requirements.txt

Логове
~~~~~~

Скриптът генерира подробни логове. За повече информация добавете:

.. code-block:: bash

   python3 supervisor.py config.conf --verbose 2>&1 | tee supervisor.log

Принос
------

Приветстваме вашия принос! Моля:

1. Fork-нете проекта
2. Създайте feature branch
3. Commit-нете промените
4. Push-нете към branch-а
5. Създайте Pull Request

Лиценз
------

Този проект е лицензиран под MIT лиценза - вижте LICENSE файла за детайли.

Поддръжка
---------

За въпроси и поддръжка:

* Създайте issue в GitHub репозиторито
* Пишете на email: support@example.com
* Документация: https://docs.example.com

Версии
------

* **v1.0.0** - Първоначална версия
* **v1.1.0** - Добавена Enterprise поддръжка
* **v1.2.0** - Init container режим
* **v1.3.0** - Подобрена OCA интеграция

Автори
------

* **Основен разработчик** - Първоначална работа
* **Общност** - Различни подобрения и поправки

Вижте пълния списък с `contributors <https://github.com/rosenvladimirov/supervisor/contributors>`_.