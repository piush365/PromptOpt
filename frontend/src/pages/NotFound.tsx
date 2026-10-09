import { Link } from "react-router-dom";
import { Compass } from "lucide-react";
import { EmptyState } from "@/components/Feedback";
import { Button } from "@/components/ui/button";

export default function NotFound() {
  return (
    <EmptyState icon={<Compass />} title="This page doesn't exist" className="mt-10"
      action={<Button asChild variant="primary"><Link to="/">Go to Optimize</Link></Button>}>
      Check the address, or use the menu to pick a page.
    </EmptyState>
  );
}
