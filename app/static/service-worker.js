self.addEventListener(
    "push",
    function (event) {

        let payload = {};

        try {

            payload =
                event.data
                    ? event.data.json()
                    : {};

        } catch (error) {

            payload = {
                title:
                    "NOVA Personal",

                body:
                    event.data
                        ? event.data.text()
                        : "Tienes una nueva notificación."
            };
        }


        const title =
            payload.title
            || "NOVA Personal";


        const options = {

            body:
                payload.body
                || "",

            tag:
                payload.tag
                || "nova",

            renotify:
                true,

            data: {
                url:
                    payload.url
                    || "/"
            }
        };


        event.waitUntil(
            self.registration
                .showNotification(
                    title,
                    options
                )
        );
    }
);


self.addEventListener(
    "notificationclick",
    function (event) {

        event.notification.close();


        const relativeUrl =
            (
                event.notification
                .data
                && event.notification
                    .data.url
            )
                ? event.notification
                    .data.url
                : "/";


        const targetUrl =
            new URL(
                relativeUrl,
                self.location.origin
            ).href;


        event.waitUntil(

            clients.matchAll({
                type: "window",
                includeUncontrolled: true
            })
            .then(
                async function (
                    windowClients
                ) {

                    for (
                        const client
                        of windowClients
                    ) {

                        if (
                            client.url
                                .startsWith(
                                    self.location.origin
                                )
                        ) {

                            if (
                                "navigate"
                                in client
                            ) {

                                await client.navigate(
                                    targetUrl
                                );
                            }

                            return client.focus();
                        }
                    }


                    return clients.openWindow(
                        targetUrl
                    );
                }
            )
        );
    }
);