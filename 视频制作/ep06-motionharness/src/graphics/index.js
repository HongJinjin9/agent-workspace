// 图形场景注册表（dispatcher）
import "./graphics.css";
import { mount as cover } from "./cover.js";
import { mount as act_title } from "./act_title.js";
import { mount as quote_feng } from "./quote_feng.js";
import { mount as quote_li } from "./quote_li.js";
import { mount as bar_compare } from "./bar_compare.js";
import { mount as data_curve } from "./data_curve.js";
import { mount as evidence_card } from "./evidence_card.js";
import { mount as statement } from "./statement.js";
import { mount as year_montage } from "./year_montage.js";
import { mount as end_card } from "./end_card.js";

export const GRAPHICS = {
  cover,
  act_title,
  quote_feng,
  quote_li,
  bar_compare,
  data_curve,
  evidence_card,
  statement,
  year_montage,
  end_card,
};

export function mountGraphic(name, ctx) {
  const fn = GRAPHICS[name];
  if (!fn) throw new Error("unknown graphic scene: " + name);
  return fn(ctx);
}
