CREATE TABLE "installations" (
	"id" text PRIMARY KEY NOT NULL,
	"last_seen" timestamp with time zone NOT NULL,
	"created_at" timestamp with time zone DEFAULT now()
);
--> statement-breakpoint
CREATE TABLE "measurements" (
	"id" serial PRIMARY KEY NOT NULL,
	"installation_id" text NOT NULL,
	"captured_at" timestamp with time zone NOT NULL,
	"pushed_at" timestamp with time zone DEFAULT now(),
	"chlorine_status" text NOT NULL,
	"chlorine_diagnosis" text,
	"chlorine_pattern" text,
	"chlorine_blinking" jsonb,
	"chlorine_solid" jsonb,
	"chlorine_summary" text,
	"chlorine_action" boolean DEFAULT false NOT NULL,
	"chlorine_recommended" text,
	"ph_status" text NOT NULL,
	"ph_diagnosis" text,
	"ph_pattern" text,
	"ph_blinking" jsonb,
	"ph_solid" jsonb,
	"ph_summary" text,
	"ph_action" boolean DEFAULT false NOT NULL,
	"ph_recommended" text,
	"raw_response" text
);
--> statement-breakpoint
ALTER TABLE "measurements" ADD CONSTRAINT "measurements_installation_id_installations_id_fk" FOREIGN KEY ("installation_id") REFERENCES "public"."installations"("id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
CREATE INDEX "idx_measurements_inst_captured" ON "measurements" USING btree ("installation_id","captured_at");