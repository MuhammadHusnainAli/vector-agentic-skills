import { Button as DsButton, Dialog } from "@acme/ui";
import { Button } from "../components/Button";
import { Btn } from "../components/Btn";
import { PrimaryButton } from "../components/PrimaryButton";
import Card from "../components/Card";
import { Modal } from "../components/Modal";
export default function Home() {
  return (<main>
    <Card title="A" /><Card title="B" />
    <Button>Save</Button><Btn>Cancel</Btn><PrimaryButton>Go</PrimaryButton><DsButton>Ok</DsButton>
    <Dialog open /><Modal open /><UserAvatar />
  </main>);
}
