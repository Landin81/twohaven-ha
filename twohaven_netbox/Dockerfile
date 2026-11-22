ARG BUILD_FROM
FROM golang:1.22-alpine AS build
WORKDIR /src
COPY src/ ./
RUN CGO_ENABLED=0 go build -trimpath -ldflags="-s -w" -o /thnet .

FROM $BUILD_FROM
RUN apk add --no-cache jq
COPY --from=build /thnet /usr/bin/thnet
COPY run.sh /run.sh
RUN chmod +x /run.sh
CMD [ "/run.sh" ]
