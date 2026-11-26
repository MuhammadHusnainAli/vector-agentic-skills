import { Button } from "@acme/ui";
import { DataGrid } from "@mui/material";
import { UserRow } from "@/components/UserRow";
export default function Users() {
  return (<section style={{ color: "#333", background: "#fafafa" }}>
    <button className="btn">Invite</button><input type="search" /><table><tbody><tr><td>x</td></tr></tbody></table>
    <DataGrid /><UserRow /><UserRow /><Button>Export</Button>
  </section>);
}
