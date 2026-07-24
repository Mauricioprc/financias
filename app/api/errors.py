import logging

from flask import Flask, jsonify
from marshmallow import ValidationError as SchemaValidationError

from app.services.exceptions import ServiceError

logger = logging.getLogger(__name__)


def register_error_handlers(app: Flask) -> None:
    @app.errorhandler(ServiceError)
    def handle_service_error(error: ServiceError):
        return (
            jsonify(
                {"error": {"code": error.code, "message": error.message, "details": error.details}}
            ),
            error.status_code,
        )

    @app.errorhandler(SchemaValidationError)
    def handle_schema_validation_error(error: SchemaValidationError):
        return (
            jsonify(
                {
                    "error": {
                        "code": "VALIDATION_ERROR",
                        "message": "Dados de entrada inválidos.",
                        "details": error.messages,
                    }
                }
            ),
            422,
        )

    @app.errorhandler(404)
    def handle_not_found(error):
        return (
            jsonify(
                {
                    "error": {
                        "code": "NOT_FOUND",
                        "message": "Recurso não encontrado.",
                        "details": {},
                    }
                }
            ),
            404,
        )

    @app.errorhandler(Exception)
    def handle_unexpected_error(error: Exception):
        logger.exception("Erro não tratado")
        return (
            jsonify(
                {
                    "error": {
                        "code": "INTERNAL_ERROR",
                        "message": "Erro interno do servidor.",
                        "details": {},
                    }
                }
            ),
            500,
        )
