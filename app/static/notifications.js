(function () {

    "use strict";


    function urlBase64ToUint8Array(
        base64String
    ) {

        const padding =
            "=".repeat(
                (
                    4
                    - base64String.length % 4
                ) % 4
            );


        const base64 =
            (
                base64String
                + padding
            )
            .replace(
                /-/g,
                "+"
            )
            .replace(
                /_/g,
                "/"
            );


        const rawData =
            window.atob(
                base64
            );


        return Uint8Array.from(
            [...rawData].map(
                function (character) {

                    return character
                        .charCodeAt(0);
                }
            )
        );
    }


    function getDeviceName() {

        const platform =
            navigator.platform
            || "Dispositivo";

        return (
            platform
            + " · "
            + navigator.userAgent
                .split(" ")
                .slice(-2)
                .join(" ")
        );
    }


    async function readResponse(
        response
    ) {

        let data = {};

        try {

            data =
                await response.json();

        } catch (error) {

            data = {};
        }


        if (!response.ok) {

            throw new Error(
                data.detail
                || data.message
                || (
                    "Error HTTP "
                    + response.status
                )
            );
        }


        return data;
    }


    async function postJson(
        url,
        payload
    ) {

        const response =
            await fetch(
                url,
                {
                    method: "POST",

                    headers: {
                        "Content-Type":
                            "application/json"
                    },

                    body:
                        JSON.stringify(
                            payload
                        )
                }
            );


        return readResponse(
            response
        );
    }


    function setStatus(
        element,
        message,
        state
    ) {

        element.textContent =
            message;

        element.className =
            "nova-push-status "
            + (
                state
                ? "is-" + state
                : ""
            );
    }


    function setButtons(
        subscribed,
        enableButton,
        testButton,
        disableButton
    ) {

        enableButton.disabled =
            subscribed;

        testButton.disabled =
            !subscribed;

        disableButton.disabled =
            !subscribed;
    }


    document.addEventListener(
        "DOMContentLoaded",
        async function () {

            const root =
                document.getElementById(
                    "novaPushSettings"
                );


            if (!root) {
                return;
            }


            const enableButton =
                document.getElementById(
                    "novaPushEnable"
                );

            const testButton =
                document.getElementById(
                    "novaPushTest"
                );

            const disableButton =
                document.getElementById(
                    "novaPushDisable"
                );

            const status =
                document.getElementById(
                    "novaPushStatus"
                );

            const deviceCount =
                document.getElementById(
                    "novaPushDeviceCount"
                );


            const publicKey =
                root.dataset.publicKey
                || "";


            if (
                !("serviceWorker"
                    in navigator)
                || !("PushManager"
                    in window)
                || !("Notification"
                    in window)
            ) {

                setStatus(
                    status,
                    (
                        "Este navegador no "
                        + "admite Web Push."
                    ),
                    "error"
                );

                return;
            }


            if (
                !window.isSecureContext
            ) {

                setStatus(
                    status,
                    (
                        "Web Push requiere "
                        + "HTTPS o localhost."
                    ),
                    "error"
                );

                return;
            }


            if (!publicKey) {

                setStatus(
                    status,
                    (
                        "No existe una "
                        + "llave VAPID pública."
                    ),
                    "error"
                );

                return;
            }


            let registration;

            try {

                registration =
                    await navigator
                        .serviceWorker
                        .register(
                            "/service-worker.js"
                        );


                await navigator
                    .serviceWorker
                    .ready;


                const existing =
                    await registration
                        .pushManager
                        .getSubscription();


                if (existing) {

                    /*
                    * El navegador ya tiene una suscripción Push.
                    *
                    * La volvemos a registrar en NOVA para asociarla
                    * al usuario que actualmente inició sesión.
                    *
                    * Esto es especialmente importante en nuestras
                    * pruebas locales, porque estamos entrando con
                    * distintos empleados desde la misma PC.
                    */
                    await postJson(
                        "/api/notificaciones/suscribir",
                        {
                            subscription:
                                existing.toJSON(),

                            device_name:
                                getDeviceName(),

                            user_agent:
                                navigator.userAgent
                        }
                    );


                    setStatus(
                        status,
                        (
                            "Notificaciones "
                            + "activadas en "
                            + "este dispositivo."
                        ),
                        "success"
                    );


                    setButtons(
                        true,
                        enableButton,
                        testButton,
                        disableButton
                    );

                } else {

                    if (
                        Notification
                            .permission
                        === "denied"
                    ) {

                        setStatus(
                            status,
                            (
                                "Las notificaciones "
                                + "están bloqueadas "
                                + "en el navegador."
                            ),
                            "error"
                        );

                    } else {

                        setStatus(
                            status,
                            (
                                "Este dispositivo "
                                + "todavía no está "
                                + "registrado."
                            ),
                            "neutral"
                        );
                    }


                    setButtons(
                        false,
                        enableButton,
                        testButton,
                        disableButton
                    );
                }

            } catch (error) {

                console.error(
                    error
                );

                setStatus(
                    status,
                    (
                        "No se pudo registrar "
                        + "el Service Worker: "
                        + error.message
                    ),
                    "error"
                );

                return;
            }


            enableButton
                .addEventListener(
                    "click",
                    async function () {

                        enableButton.disabled =
                            true;

                        setStatus(
                            status,
                            (
                                "Activando "
                                + "notificaciones..."
                            ),
                            "neutral"
                        );


                        try {

                            const permission =
                                await Notification
                                    .requestPermission();


                            if (
                                permission
                                !== "granted"
                            ) {

                                throw new Error(
                                    (
                                        "No se autorizó "
                                        + "el permiso de "
                                        + "notificaciones."
                                    )
                                );
                            }


                            let subscription =
                                await registration
                                    .pushManager
                                    .getSubscription();


                            if (
                                !subscription
                            ) {

                                subscription =
                                    await registration
                                        .pushManager
                                        .subscribe({
                                            userVisibleOnly:
                                                true,

                                            applicationServerKey:
                                                urlBase64ToUint8Array(
                                                    publicKey
                                                )
                                        });
                            }


                            await postJson(
                                (
                                    "/api/"
                                    + "notificaciones/"
                                    + "suscribir"
                                ),
                                {
                                    subscription:
                                        subscription
                                            .toJSON(),

                                    device_name:
                                        getDeviceName(),

                                    user_agent:
                                        navigator
                                            .userAgent
                                }
                            );


                            setStatus(
                                status,
                                (
                                    "Notificaciones "
                                    + "activadas "
                                    + "correctamente."
                                ),
                                "success"
                            );


                            setButtons(
                                true,
                                enableButton,
                                testButton,
                                disableButton
                            );

                            if (deviceCount) {
                                const current =
                                    Number(
                                        deviceCount.textContent
                                    ) || 0;

                                if (current < 1) {
                                    deviceCount.textContent = "1";
                                }
                            }


                        } catch (error) {

                            console.error(
                                error
                            );


                            setStatus(
                                status,
                                error.message,
                                "error"
                            );


                            enableButton.disabled =
                                false;
                        }
                    }
                );


            testButton
                .addEventListener(
                    "click",
                    async function () {

                        testButton.disabled =
                            true;


                        try {

                            const subscription =
                                await registration
                                    .pushManager
                                    .getSubscription();


                            if (
                                !subscription
                            ) {

                                throw new Error(
                                    (
                                        "Primero activa "
                                        + "las "
                                        + "notificaciones."
                                    )
                                );
                            }


                            const result =
                                await postJson(
                                    (
                                        "/api/"
                                        + "notificaciones/"
                                        + "prueba"
                                    ),
                                    {
                                        endpoint:
                                            subscription
                                                .endpoint
                                    }
                                );


                            setStatus(
                                status,
                                result.message,
                                "success"
                            );


                        } catch (error) {

                            console.error(
                                error
                            );


                            setStatus(
                                status,
                                error.message,
                                "error"
                            );

                        } finally {

                            testButton.disabled =
                                false;
                        }
                    }
                );


            disableButton
                .addEventListener(
                    "click",
                    async function () {

                        disableButton.disabled =
                            true;


                        try {

                            const subscription =
                                await registration
                                    .pushManager
                                    .getSubscription();


                            if (
                                subscription
                            ) {

                                await postJson(
                                    (
                                        "/api/"
                                        + "notificaciones/"
                                        + "desuscribir"
                                    ),
                                    {
                                        endpoint:
                                            subscription
                                                .endpoint
                                    }
                                );


                                await subscription
                                    .unsubscribe();
                            }


                            setStatus(
                                status,
                                (
                                    "Notificaciones "
                                    + "desactivadas "
                                    + "en este dispositivo."
                                ),
                                "neutral"
                            );


                            setButtons(
                                false,
                                enableButton,
                                testButton,
                                disableButton
                            );

                            if (deviceCount) {
                                deviceCount.textContent = "0";
                            }


                        } catch (error) {

                            console.error(
                                error
                            );


                            setStatus(
                                status,
                                error.message,
                                "error"
                            );


                            disableButton.disabled =
                                false;
                        }
                    }
                );
        }
    );

})();