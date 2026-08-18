from base64 import urlsafe_b64encode
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec


ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"

PRIVATE_KEY_PATH = DATA_DIR / "nova_vapid_private.pem"
PUBLIC_KEY_PATH = DATA_DIR / "nova_vapid_public.txt"


def main():
    DATA_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    if (
        PRIVATE_KEY_PATH.exists()
        or PUBLIC_KEY_PATH.exists()
    ):
        print(
            "Ya existen llaves VAPID."
        )

        print(
            f"Privada: {PRIVATE_KEY_PATH}"
        )

        print(
            f"Pública: {PUBLIC_KEY_PATH}"
        )

        if PUBLIC_KEY_PATH.exists():
            print()
            print(
                "Llave pública:"
            )
            print(
                PUBLIC_KEY_PATH
                .read_text(
                    encoding="utf-8",
                )
                .strip()
            )

        return

    private_key = (
        ec.generate_private_key(
            ec.SECP256R1()
        )
    )

    private_bytes = (
        private_key.private_bytes(
            encoding=(
                serialization.Encoding.PEM
            ),
            format=(
                serialization
                .PrivateFormat.PKCS8
            ),
            encryption_algorithm=(
                serialization.NoEncryption()
            ),
        )
    )

    public_bytes = (
        private_key
        .public_key()
        .public_bytes(
            encoding=(
                serialization.Encoding.X962
            ),
            format=(
                serialization
                .PublicFormat
                .UncompressedPoint
            ),
        )
    )

    public_key = (
        urlsafe_b64encode(
            public_bytes
        )
        .decode("ascii")
        .rstrip("=")
    )

    PRIVATE_KEY_PATH.write_bytes(
        private_bytes
    )

    PUBLIC_KEY_PATH.write_text(
        public_key,
        encoding="utf-8",
    )

    print(
        "Llaves VAPID creadas correctamente."
    )

    print(
        f"Privada: {PRIVATE_KEY_PATH}"
    )

    print(
        f"Pública: {PUBLIC_KEY_PATH}"
    )

    print()
    print(
        "Llave pública:"
    )
    print(
        public_key
    )


if __name__ == "__main__":
    main()