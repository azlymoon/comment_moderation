Пользовательская документация
=============================

Этот раздел описывает, как представители сторонних веб-сервисов и сотрудники службы
модерации взаимодействуют с системой.

Авторизация администратора
--------------------------

1. Выполните запрос:

   .. code-block:: bash

      curl -X POST http://127.0.0.1:8000/auth/login \
           -H "Content-Type: application/json" \
           -d '{"username":"moderator","password":"moderator"}'

2. В ответе вы получите ``token`` и ``expires_at``. Скопируйте значение токена и используйте
его в заголовке ``X-Admin-Token`` для всех административных операций.

Рабочий процесс модератора
--------------------------

#. Просмотр списка заявок:

   .. code-block:: bash

      curl http://127.0.0.1:8000/admin/requests \
           -H "X-Admin-Token: <token>"

#. Просмотр подробностей и результата конкретной заявки:

   .. code-block:: bash

      curl http://127.0.0.1:8000/admin/requests/<request_id> \
           -H "X-Admin-Token: <token>"

#. Обновление решения (например, перевод в ручную проверку):

   .. code-block:: bash

      curl -X PATCH http://127.0.0.1:8000/admin/requests/<request_id> \
           -H "Content-Type: application/json" \
           -H "X-Admin-Token: <token>" \
           -d '{"decision":"HUMAN_REVIEW"}'

Управление категориями и правилами
----------------------------------

* Список категорий:

  .. code-block:: bash

     curl http://127.0.0.1:8000/admin/categories \
          -H "X-Admin-Token: <token>"

* Создание/обновление категории:

  .. code-block:: bash

     curl -X POST http://127.0.0.1:8000/admin/categories \
          -H "Content-Type: application/json" \
          -H "X-Admin-Token: <token>" \
          -d '{"type":"TOXICITY","name":"Abuse","description":"Общие оскорбления","auto_reject_threshold":0.95,"human_review_threshold":0.6,"is_enabled":true}'

* Добавление правила:

  .. code-block:: bash

     curl -X POST http://127.0.0.1:8000/admin/rules \
          -H "Content-Type: application/json" \
          -H "X-Admin-Token: <token>" \
          -d '{"category_id":"<category_id>","action":"FLAG_FOR_REVIEW","priority":50,"conditions":["contains:abuse"]}'

Управление веб-сервисами и API-ключами
--------------------------------------

1. Создайте запись веб-сервиса (обязательные поля – название и email):

   .. code-block:: bash

      curl -X POST http://127.0.0.1:8000/admin/services \
           -H "Content-Type: application/json" \
           -H "X-Admin-Token: <token>" \
           -d '{"name":"News Portal","description":"Комментарии читателей","contact_email":"team@news.example"}'

2. Выпишите API-ключ для нового сервиса:

   .. code-block:: bash

      curl -X POST http://127.0.0.1:8000/admin/services/<service_id>/api-keys \
           -H "X-Admin-Token: <token>"

   В ответе будет поле ``api_key`` — его нужно сохранить, повторно значение не возвращается.

3. Получите список API-ключей:

   .. code-block:: bash

      curl http://127.0.0.1:8000/admin/services/<service_id>/api-keys \
           -H "X-Admin-Token: <token>"

4. Деактивируйте или активируйте ключ:

   .. code-block:: bash

      curl -X PATCH "http://127.0.0.1:8000/admin/api-keys/<key_id>?is_active=false" \
           -H "X-Admin-Token: <token>"

Отправка комментария на модерацию
---------------------------------

Веб-сервис вызывает публичный API и передаёт собственный идентификатор сервиса и текст сообщения.

.. code-block:: bash

   curl -X POST http://127.0.0.1:8000/api/v1/moderation/text \
        -H "Content-Type: application/json" \
        -H "X-API-Key: <plain_api_key>" \
        -d '{"service_id":"<service_id>","content_text":"I totally hate this!"}'

В ответе возвращается объект ``ModerationResponse`` со статусом заявки, решением и метаданными
ML-модели (вероятности по категориям).

Получение статистики
--------------------

.. code-block:: bash

   curl http://127.0.0.1:8000/admin/statistics/<service_id> \
        -H "X-Admin-Token: <token>"

Ответ содержит сводные показатели: число обработанных запросов, распределение решений, количество
заявок в ожидании.
