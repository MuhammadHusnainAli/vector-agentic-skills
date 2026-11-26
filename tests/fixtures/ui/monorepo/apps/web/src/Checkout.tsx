import { Button, TextField, Dialog } from "@acme/ui";
import { PriceRow } from "./PriceRow";
export function Checkout() {
  return (<form>
    <TextField label="Email" /><TextField label="Card" />
    <PriceRow /><Dialog open={false} />
    <Button variant="primary">Pay</Button>
  </form>);
}
