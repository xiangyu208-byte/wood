FROM maven:3.9.9-eclipse-temurin-17 AS builder

WORKDIR /workspace
COPY .mvn ./.mvn
COPY mvnw pom.xml ./
RUN chmod +x mvnw
COPY src ./src
RUN --mount=type=cache,target=/root/.m2 ./mvnw -B -DskipTests package

FROM eclipse-temurin:17-jre-alpine

RUN addgroup -S -g 10001 app && adduser -S -u 10001 app -G app \
    && mkdir -p /data/uploads \
    && chown -R app:app /data/uploads

WORKDIR /app
COPY --from=builder /workspace/target/wood-detect-*.jar app.jar

USER app
EXPOSE 8080
ENTRYPOINT ["java", "-jar", "/app/app.jar"]
