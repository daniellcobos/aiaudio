from uuid import uuid4

from sqlalchemy.orm import validates
from werkzeug.security import check_password_hash, generate_password_hash

from login import login_manager
from sqla import sqla
from flask_login import UserMixin


class User(UserMixin, sqla.Model):
    __tablename__ = 'dt_usuario_cubo'
    id = sqla.Column(sqla.Integer, primary_key=True)
    uuid = sqla.Column(sqla.String(64), nullable=False, default=lambda: str(uuid4()))
    username = sqla.Column(sqla.Text, nullable=False, unique=True)
    password = sqla.Column(sqla.Text, nullable=False)
    client = sqla.Column(sqla.Text, nullable=False)
    nivel = sqla.Column(sqla.Integer, nullable = True, unique = False)
    activo = sqla.Column(sqla.Integer, nullable=True)


    @validates('username', 'password')
    def validate_not_empty(self, key, value):
        if not value:
            raise ValueError(f'{key.capitalize()} is required.')

        if key == 'username':
            self.validate_unique(key, value, f'{value} already registered')

        if key == 'password':
            value = generate_password_hash(value)

        return value

    def validate_unique(self, key, value, error_message=None):
        if (
                User.query.filter_by(**{key: value}).first()
                is not None
        ):
            if not error_message:
                error_message = f'{key} must be unique.'
            raise ValueError(error_message)

        return value

    def correct_password(self, plaintext):
        return check_password_hash(self.password, plaintext)

    def get_id(self):
        return self.uuid

    def __repr__(self):
        return self.username

    def is_confirmed(self):
        return self.activo

    def getClient(self):
        return  self.client
    def getNivel(self):
        return  self.nivel

@login_manager.user_loader
def load_user(user_uuid):
    return User.query.filter_by(uuid=user_uuid).first()
