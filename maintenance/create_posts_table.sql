CREATE TABLE IF NOT EXISTS public.posts
(
    "postId" bigint NOT NULL GENERATED ALWAYS AS IDENTITY ( INCREMENT 1 START 1000 MINVALUE 1 MAXVALUE 9223372036854775807 CACHE 1 ),
    "userId" character varying(50) COLLATE pg_catalog."default",
    "videoId" character varying(50) COLLATE pg_catalog."default",
    platform character varying(50) COLLATE pg_catalog."default",
    "postDateTime" timestamp without time zone,
    "discordMessageId" character varying(50) COLLATE pg_catalog."default",
    CONSTRAINT post_id PRIMARY KEY ("postId")
)
