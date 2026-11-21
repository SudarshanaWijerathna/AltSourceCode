"use client";
// Every UI card Mira can show, with realistic sample data, on one page (/cards) for styling.
// Uses the real components and the real CSS, so a style change here is a change in the chat too.
import { Fragment } from "react";
import {
  BookingForm,
  ChildAgesPicker,
  DatePicker,
  ItineraryDay,
  PriceBreakdown,
  SourceList,
  SpecialistHandoff,
  TourCard,
  TravellerPicker,
} from "@/components/catalog/cards";
import { WelcomeBack } from "@/components/WelcomeBack";

const SRC = "docs/ceylon-compass-dataset/content";
const sigiriya = {
  tour_id: "T01",
  title: "Sigiriya and Minneriya Day Tour from Kandy",
  duration: "1 day",
  summary: "A long, rewarding day from Kandy into the Cultural Triangle: climb the Sigiriya rock fortress in the morning, then look for wild elephants on an afternoon jeep safari in Minneriya National Park.",
  source_path: `${SRC}/tours/sigiriya-minneriya-day-tour-from-kandy.md`,
};
const lastQuote = {
  enquiry_id: "ENQ-PREVIEW", tour_id: "T09", tour_title: "Cultural Triangle Sri Lanka Package",
  start_date: "2027-05-03", adults: 2, children: 0, infants: 0, booked: false,
};

type Item = { name: string; component: string; when: string; node: React.ReactNode };

const ITEMS: Item[] = [
  { name: "Tour card (suggestion)", component: "tour_card", when: "A suggested tour the traveller can pick",
    node: <TourCard {...sigiriya} action="choose" /> },
  { name: "Tour card (chosen)", component: "tour_card", when: "The chosen tour: shown once, no button",
    node: <TourCard {...sigiriya} action={null} /> },
  { name: "Who's travelling", component: "traveller_picker", when: "Travellers missing (Continue / Get my price)",
    node: <TravellerPicker prompt="Who is travelling?" final={false} /> },
  { name: "Start date", component: "date_picker", when: "Start date missing; last detail → Get my price",
    node: <DatePicker prompt="When would you like to start?" min_date="2026-11-19" max_date="2027-10-31" final /> },
  { name: "Children's ages", component: "child_ages_picker", when: "Children given without ages",
    node: <ChildAgesPicker count={2} final /> },
  { name: "Itinerary day", component: "itinerary_day", when: "After a multi-day tour is priced (one per day)",
    node: <ItineraryDay day={4} title="Sigiriya and Polonnaruwa" source_path={`${SRC}/tours/cultural-triangle-6-nights.md`}
      description="Sigiriya at sunrise, Polonnaruwa in the afternoon. · Meals: Breakfast, dinner · Accommodation: Sigiriya Village or similar · Entrance tickets included: Sigiriya, Polonnaruwa" /> },
  { name: "Your price (pay in full)", component: "price_breakdown", when: "Day tour, or starts within 30 days",
    node: <PriceBreakdown quote_id="ENQ-PREVIEW1" price_usd={315} deposit_usd={315} balance_usd={0} balance_due={null} /> },
  { name: "Your price (deposit)", component: "price_breakdown", when: "Multi-day tour more than 30 days ahead",
    node: <PriceBreakdown quote_id="ENQ-PREVIEW2" price_usd={2125} deposit_usd={532} balance_usd={1593} balance_due="2027-04-03" /> },
  { name: "Reserve this trip", component: "booking_form", when: "Shown with every price",
    node: <BookingForm quote_id="ENQ-PREVIEW1" /> },
  { name: "Booked", component: "booking_form (result)", when: "After Pay deposit and book succeeds",
    node: <BookingForm quote_id="ENQ-PREVIEW1" preview={{ status: "confirmed", booking_ref: "CC-1A2B3C", deposit_usd: "315",
      message: "Booked. Your reference is CC-1A2B3C. We've taken your deposit of USD 315 (test mode).",
      next_step: "You'll receive a confirmation email with your itinerary and payment schedule." }} /> },
  { name: "Not booked yet", component: "booking_form (result)", when: "Card declined / booking system down",
    node: <BookingForm quote_id="ENQ-PREVIEW1" preview={{ status: "payment_failed",
      message: "Your card wasn't charged: the payment was declined by the bank.",
      next_step: "You can try another card, or we can hold this price and send you a secure payment link by email. Our team has your details and will follow up." }} /> },
  { name: "Passed to our team", component: "specialist_handoff", when: "No price possible (missing/expired rates, >20 people, not in catalogue)",
    node: <SpecialistHandoff message="A travel specialist will check this trip and confirm your price." /> },
  { name: "Sources", component: "source_list", when: "Mira answers from our tour and policy pages",
    node: <SourceList sources={[
      { title: "Galle Fort Walking Tour", source_path: `${SRC}/tours/galle-fort-walking-tour.md` },
      { title: "Cancellation policy", source_path: `${SRC}/policies/cancellation-policy.md` },
    ]} /> },
];

export function CardGallery() {
  return (
    <div className="gallery">
      <header className="gallery__head">
        <h1>Mira UI cards</h1>
        <p className="muted">All cards with sample data, rendered by the real components and CSS (<code>app/globals.css</code>). Dev-only page.</p>
      </header>

      <section className="gallery__section">
        <h2>Welcome-back notification <span className="muted">(page UI, returning visitors)</span></h2>
        <div className="gallery__wide">
          <WelcomeBack q={{ ...lastQuote, still_valid: true, price_usd: "2125", deposit_usd: "532" }} />
          <WelcomeBack q={{ ...lastQuote, enquiry_id: "ENQ-PREVIEW-B", still_valid: false, price_usd: null, deposit_usd: null }} />
        </div>
      </section>

      <section className="gallery__section">
        <h2>Catalog cards <span className="muted">(sent by Mira as show_&lt;component&gt;)</span></h2>
        <div className="gallery__grid">
          {ITEMS.map((it) => (
            <figure key={it.name} className="gallery__item">
              <figcaption>
                <strong>{it.name}</strong> <code>{it.component}</code>
                <span className="muted">{it.when}</span>
              </figcaption>
              {it.node}
            </figure>
          ))}
        </div>
      </section>

      <section className="gallery__section">
        <h2>Phone width <span className="muted">(390px)</span></h2>
        <div className="gallery__phone">
          {ITEMS.filter((it) => !["Tour card (chosen)", "Your price (pay in full)"].includes(it.name)).map((it) => <Fragment key={it.name}>{it.node}</Fragment>)}
        </div>
      </section>
    </div>
  );
}
