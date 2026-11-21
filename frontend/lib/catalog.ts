// Client-side mirror of backend/mira/ui/catalog.py. Payloads are validated again here
// before rendering; anything not in the catalog is dropped.
import { z } from "zod";

export const Component = z.discriminatedUnion("component", [
  z.object({ component: z.literal("traveller_picker"), prompt: z.string(), options: z.array(z.enum(["solo", "couple", "family", "group"])) }),
  z.object({ component: z.literal("tour_card"), tour_id: z.string(), title: z.string(), duration: z.string(), summary: z.string(), source_path: z.string() }),
  z.object({ component: z.literal("itinerary_day"), day: z.number().int().min(1), title: z.string(), description: z.string(), source_path: z.string() }),
  z.object({ component: z.literal("price_breakdown"), quote_id: z.string(), price_usd: z.number(), deposit_usd: z.number(), balance_usd: z.number().default(0), balance_due: z.string().nullable().default(null) }),
  z.object({ component: z.literal("booking_form"), quote_id: z.string() }),
  z.object({ component: z.literal("specialist_handoff"), message: z.string() }),
]);
export type Component = z.infer<typeof Component>;
