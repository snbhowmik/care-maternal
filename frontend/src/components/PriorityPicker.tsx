import { Button } from "@/components/careui/button";
import { Field, FieldLabel } from "@/components/careui/field";
import { PRIORITIES, priorityMeta } from "@/types";
import type { Priority } from "@/types";

/** Choose how urgent a check is. The rule for the chosen priority is shown, so nobody has to guess. */
export default function PriorityPicker({ value, onChange }: { value: Priority; onChange: (p: Priority) => void }) {
  return (
    <Field>
      <FieldLabel>Priority</FieldLabel>
      <div className="flex flex-wrap gap-2" role="radiogroup" aria-label="Priority">
        {PRIORITIES.map((p) => (
          <Button key={p.value} type="button" size="sm" role="radio" aria-checked={value === p.value}
            variant={value === p.value ? "default" : "outline"} onClick={() => onChange(p.value)}>
            {p.label}
          </Button>
        ))}
      </div>
      <p className="text-xs text-muted-foreground">{priorityMeta(value).rule}</p>
    </Field>
  );
}
