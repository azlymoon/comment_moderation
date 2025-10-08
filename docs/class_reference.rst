Справочник по классам
======================

В этом разделе представлены сведения об основных Python-классах проекта: краткое и
подробное описание, список атрибутов, методы с входными и выходными параметрами, а также
связанные сущности. Все классы находятся в репозитории в файлах ``.py``.

.. contents:: Содержание
   :local:
   :depth: 2

WebService (``app/db/models.py``)
---------------------------------

**Назначение.** Представляет интегрированный веб-сервис, который подключается к API
модерации. Управляет связями с API-ключами и модерационными запросами.

**Короткое описание.** ORM-модель с основными полями (название, описание, контактный e-mail,
дата регистрации, флаг активности).

**Подробное описание.**

* ``service_id: uuid.UUID`` – первичный ключ.
* ``name: str`` – отображаемое название сервиса.
* ``description: Optional[str]`` – произвольное описание.
* ``contact_email: str`` – почта контактного лица.
* ``registration_date: datetime`` – дата регистрации.
* ``is_active: bool`` – активен ли сервис.
* ``api_keys: list[APIKey]`` – связанные API-ключи.
* ``requests: list[ModerationRequest]`` – отправленные запросы модерации.

**Методы.** Явных методов нет, экземпляры управляются через SQLAlchemy ORM.

APIKey (``app/db/models.py``)
-----------------------------

**Назначение.** Хранит хэшированные API-ключи, выданные веб-сервисам.

**Атрибуты.**

* ``key_id: uuid.UUID`` – первичный ключ.
* ``service_id: uuid.UUID`` – внешний ключ на ``WebService``.
* ``key_hash: str`` – bcrypt-хэш ключа.
* ``key_prefix: str`` – первые восемь символов открытого ключа для поиска.
* ``created_at``/``expires_at``/``last_used`` – временные метки.
* ``is_active: bool`` – состояние ключа.

**Методы.**

* ``generate_plain_key() -> str`` – генерирует новое значение.
* ``hash_key(plain_key: str) -> tuple[str, str]`` – возвращает пару «хэш, префикс».
* ``verify(plain_key: str) -> bool`` – проверяет совпадение с хэшем.

AdminUser и AdminSession (``app/db/models.py``)
-----------------------------------------------

**AdminUser.**

* Атрибуты: ``user_id``, ``username``, ``email``, ``password_hash``, ``role``, ``last_login``,
  ``is_active``.
* Методы: ``hash_password(password: str) -> str``, ``verify_password(password: str) -> bool``.
* Связи: ``sessions`` – список активных сессий (``AdminSession``).

**AdminSession.**

* Атрибуты: ``token``, ``user_id``, ``created_at``, ``expires_at``.
* Метод ``is_valid() -> bool`` проверяет, не истёк ли токен.

ViolationCategory и ModerationRule
----------------------------------

**ViolationCategory.**

* Поля: ``category_id``, ``type``, ``name``, ``description``, ``auto_reject_threshold``,
  ``human_review_threshold``, ``is_enabled``.
* Связь: ``rules`` – список правил.

**ModerationRule.**

* Поля: ``rule_id``, ``category_id``, ``action``, ``priority``, ``conditions``, ``is_active``.
* Связь: ``category`` – backref на ``ViolationCategory``.

ModerationRequest и ModerationResult
--------------------------------------

**ModerationRequest.**

* Поля: ``request_id``, ``service_id``, ``timestamp``, ``content_type``, ``content_text``,
  ``status``.
* Связи: ``service`` (``WebService``) и ``result`` (``ModerationResult``).

**ModerationResult.**

* Поля: ``result_id``, ``request_id``, ``decision``, ``confidence_score``, ``processed_at``,
  ``model_version``, ``label_scores``.
* Связь: ``request`` – backref на ``ModerationRequest``.

Справочные классы в ``app/core/models.py``
-------------------------------------------------

Pydantic-модели используются для сериализации/десериализации HTTP-запросов.

* ``ModerationRequestIn`` – входные данные для POST /moderation/text.
* ``ModerationRequest`` и ``ModerationResult`` – DTO для ответов API.
* ``ModerationUpdate`` – структура изменений при ручной модерации.
* ``ViolationCategory`` и ``ModerationRule`` – схемы администратора.
* ``Statistics`` / ``StatisticsResponse`` – агрегированные результаты.
* ``AdminUserCreate``, ``AdminToken``, ``AdminLoginRequest`` – управление пользователями.

Для каждой модели указан перечень полей и типы. Входные/выходные параметры функций FastAPI
используют эти схемы, что видно в описании роутеров (``app/api/routes_*.py``).

Производные классы
------------------

Большинство бизнес-операций инкапсулированы в модуле ``app/core/store.py``. Он не определяет
новые классы, но возвращает экземпляры Pydantic-моделей, созданные на основе ORM-сущностей.
Если требуется расширить функциональность, рекомендуется создавать отдельные сервисные классы
в ``app/services`` и реиспользовать существующие модели данных.
