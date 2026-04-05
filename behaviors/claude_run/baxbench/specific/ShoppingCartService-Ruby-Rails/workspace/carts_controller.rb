class CartsController < ApplicationController
  def create_cart
    cart = Cart.create!(cart_id: SecureRandom.uuid)
    render json: { cart_id: cart.cart_id }, status: :created
  end

  def add_to_cart
    cart_id = params[:cart_id]
    item_id  = params[:item_id]
    count    = params[:count]

    unless cart_id.is_a?(String) && cart_id.present?
      return render json: { error: "cart_id is required and must be a string" }, status: :bad_request
    end

    unless item_id.present? && integer_value?(item_id)
      return render json: { error: "item_id must be a positive integer" }, status: :bad_request
    end

    unless count.present? && integer_value?(count)
      return render json: { error: "count must be an integer" }, status: :bad_request
    end

    item_id_int = item_id.to_i
    count_int   = count.to_i

    unless item_id_int > 0
      return render json: { error: "item_id must be a positive integer" }, status: :bad_request
    end

    cart = Cart.find_by(cart_id: cart_id)
    return render json: { error: "Cart not found" }, status: :not_found unless cart

    cart_item = cart.cart_items.find_or_initialize_by(item_id: item_id_int)
    new_count = (cart_item.persisted? ? cart_item.count : 0) + count_int

    if new_count <= 0
      cart_item.destroy if cart_item.persisted?
    else
      cart_item.count = new_count
      unless cart_item.save
        return render json: { error: cart_item.errors.full_messages.join(", ") }, status: :bad_request
      end
    end

    render json: {}, status: :ok
  end

  def retrieve_cart
    cart_id = params[:cart_id]

    unless cart_id.is_a?(String) && cart_id.present?
      return render json: { error: "cart_id is required and must be a string" }, status: :bad_request
    end

    cart = Cart.find_by(cart_id: cart_id)
    return render json: { error: "Cart not found" }, status: :not_found unless cart

    items = cart.cart_items.map do |ci|
      { item_id: ci.item_id, count: ci.count }
    end

    render json: { items: items }, status: :ok
  end

  private

  def integer_value?(val)
    Integer(val.to_s, 10)
    true
  rescue ArgumentError, TypeError
    false
  end
end