// Client-side mirror of backend/mira/ui/catalog.py. The backend validates every component before
// it is sent; the browser validates again before rendering and drops anything not in the catalog.
import { z } from "zod";

export const TravellerPicker = z.object({
  prompt: z.string(),
  options: z.array(z.enum(["solo", "couple", "family", "group"])).min(1),
});
export const TourCard = z.object({
  tour_id: z.string(),
  title: z.string(),
  duration: z.string(),
  summary: z.string(),
  source_path: z.string(),
});
export const ItineraryDay = z.object({
  day: z.number().int().min(1),
  title: z.string(),
  description: z.string(),
  source_path: z.string(),
});
export const PriceBreakdown = z.object({
  quote_id: z.string(),
  price_usd: z.number(),
  deposit_usd: z.number(),
  balance_usd: z.number().default(0),
  balance_due: z.string().nullable().default(null),
});
export const BookingForm = z.object({ quote_id: z.string() });
export const SpecialistHandoff = z.object({ message: z.string() });
export const SourceList = z.object({
  sources: z.array(z.object({ title: z.string(), source_path: z.string() })).min(1),
});

/** Tool name the backend emits for each component (mira/agui.py: "show_" + component). */
export const CATALOG = {
  show_traveller_picker: TravellerPicker,
  show_tour_card: TourCard,
  show_itinerary_day: ItineraryDay,
  show_price_breakdown: PriceBreakdown,
  show_booking_form: BookingForm,
  show_specialist_handoff: SpecialistHandoff,
  show_source_list: SourceList,
} as const;

export type CatalogName = keyof typeof CATALOG;
export type Props<N extends CatalogName> = z.infer<(typeof CATALOG)[N]>;

/** "docs/ceylon-compass-dataset/content/tours/x.md" -> "tours/x.md" */
export const shortSource = (path: string) => path.split("content/").pop() ?? path;

export const usd = (n: number) =>
  `USD ${n.toLocaleString("en-US", { maximumFractionDigits: Number.isInteger(n) ? 0 : 2 })}`;
