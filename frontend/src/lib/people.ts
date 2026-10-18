// Person ids in people.json are "first-last", so a display name can be derived from the id
// for payloads that only carry ids (DM recipients, meeting attendees).
export function nameFromId(id: string): string {
  return id
    .split("-")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

export function firstName(id: string): string {
  return nameFromId(id).split(" ")[0];
}
