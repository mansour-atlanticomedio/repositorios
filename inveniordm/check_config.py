from invenio_app.factory import create_app
app = create_app()
with app.app_context():
    from flask import current_app
    print('SESSION_COOKIE_SECURE:', current_app.config.get('SESSION_COOKIE_SECURE'))
    print('SESSION_COOKIE_SAMESITE:', current_app.config.get('SESSION_COOKIE_SAMESITE'))
    print('SECRET_KEY:', str(current_app.config.get('SECRET_KEY', ''))[:15] + '...')
    print('APP_DEFAULT_SECURE_HEADERS:', current_app.config.get('APP_DEFAULT_SECURE_HEADERS', {}))
