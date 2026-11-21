"use client";
// Generative UI: Mira's backend emits one AG-UI tool call per component ("show_tour_card", ...).
// Each is rendered here with CopilotKit's useRenderTool, after validating its arguments against
// the catalog schema. Unknown tools and invalid payloads render nothing.
import { useRenderTool } from "@copilotkit/react-core/v2";
import { z } from "zod";

import {
  BookingForm,
  ItineraryDay,
  PriceBreakdown,
  SourceList,
  ChildAgesPicker,
  DatePicker,
  SpecialistHandoff,
  TourCard,
  TravellerPicker,
} from "@/components/catalog/cards";
import { CATALOG, type CatalogName } from "@/lib/catalog";

const VIEWS: { [N in CatalogName]: (props: never) => React.ReactElement } = {
  show_traveller_picker: TravellerPicker,
  show_tour_card: TourCard,
  show_itinerary_day: ItineraryDay,
  show_price_breakdown: PriceBreakdown,
  show_booking_form: BookingForm,
  show_specialist_handoff: SpecialistHandoff,
  show_source_list: SourceList,
  show_date_picker: DatePicker,
  show_child_ages_picker: ChildAgesPicker,
};

function useCatalogRenderer<N extends CatalogName>(name: N) {
  const schema = CATALOG[name];
  const View = VIEWS[name] as (props: z.infer<typeof schema>) => React.ReactElement;
  useRenderTool(
    {
      name,
      parameters: z.any(),
      render: ({ status, parameters }) => {
        if (status === "inProgress") return <div className="mira-card mira-card--loading" aria-hidden />;
        const parsed = schema.safeParse(parameters);
        if (!parsed.success) {
          console.warn(`Dropped invalid ${name} payload`, parsed.error.issues);
          return null;
        }
        return <View {...(parsed.data as z.infer<typeof schema>)} />;
      },
    },
    [],
  );
}

export function MiraRenderers() {
  useCatalogRenderer("show_traveller_picker");
  useCatalogRenderer("show_tour_card");
  useCatalogRenderer("show_itinerary_day");
  useCatalogRenderer("show_price_breakdown");
  useCatalogRenderer("show_booking_form");
  useCatalogRenderer("show_specialist_handoff");
  useCatalogRenderer("show_source_list");
  useCatalogRenderer("show_date_picker");
  useCatalogRenderer("show_child_ages_picker");
  // Anything outside the catalog is never drawn.
  useRenderTool({ name: "*", render: () => null }, []);
  return null;
}
