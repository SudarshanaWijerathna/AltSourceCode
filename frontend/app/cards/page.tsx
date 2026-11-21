// /cards — every UI card in one place for styling. Development only (404 in production builds).
import { notFound } from "next/navigation";

import { CardGallery } from "@/components/CardGallery";

export const metadata = { title: "Mira UI cards · Ceylon Compass Holidays", robots: { index: false } };

export default function CardsPage() {
  if (process.env.NODE_ENV === "production") notFound();
  return <CardGallery />;
}
