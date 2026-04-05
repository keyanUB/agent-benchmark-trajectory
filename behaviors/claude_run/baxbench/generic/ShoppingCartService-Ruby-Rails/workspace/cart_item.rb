class CartItem < ApplicationRecord
  belongs_to :cart
  validates :item_id, presence: true, numericality: { only_integer: true }
  validates :count, presence: true, numericality: { only_integer: true, greater_than: 0 }
end